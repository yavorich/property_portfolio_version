import logging
import re
from typing import Any

import httpx
from django.conf import settings

from .base import ParsedListing

logger = logging.getLogger(__name__)

# Bayut listing URLs:
#   https://www.bayut.com/property/details-13898698.html
#   https://www.bayut.com/ru/property/details-13898698.html
# The number after `/details-` is the property's externalID — the same
# value the API accepts as `?id=...`.
PROPERTY_ID_RE = re.compile(r"/details-(\d+)", re.IGNORECASE)

SQFT_TO_SQM = 0.092903


class BayutParser:
    """Bayut listing parser backed by the RapidAPI ``b_yut-data-api`` service.

    Endpoint: ``GET /property-details?id={external_id}`` with
    ``X-RapidAPI-Key`` and ``X-RapidAPI-Host`` headers.
    """

    SOURCE = "bayut"

    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def parse(self, url: str) -> ParsedListing:
        api_key = getattr(settings, "BAYUT_API_KEY", "")
        if not api_key:
            raise RuntimeError("BAYUT_API_KEY is not configured")

        property_id = self._extract_property_id(url)
        api_url = f"{settings.BAYUT_API_BASE_URL.rstrip('/')}/property-details"
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": settings.BAYUT_API_HOST,
            "Accept": "application/json",
        }

        response = await self.http.get(api_url, params={"id": property_id}, headers=headers)
        if response.status_code != 200:
            detail = response.text[:500]
            logger.error(
                "Bayut API failed: status=%s url=%s body=%s",
                response.status_code, api_url, detail,
            )
            raise RuntimeError(
                f"Bayut API returned {response.status_code}: {detail}"
            )

        payload = response.json()
        return self._to_listing(url, property_id, payload)

    @staticmethod
    def _extract_property_id(url: str) -> str:
        match = PROPERTY_ID_RE.search(url)
        if not match:
            raise ValueError(
                "Cannot extract Bayut property ID from URL — expected "
                "'/details-<id>' segment"
            )
        return match.group(1)

    def _to_listing(self, source_url: str, property_id: str, payload: dict) -> ParsedListing:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ValueError(
                f"Bayut API response missing 'data' object (got keys={list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__})"
            )

        listing = ParsedListing(
            source=self.SOURCE,
            source_url=source_url,
            raw_data=payload,
        )

        listing.title = _as_str(data.get("title"))
        listing.description = _as_str(data.get("description"))
        listing.property_type = _extract_property_type(data)
        listing.features = _extract_features(data)

        price = data.get("price")
        if isinstance(price, (int, float)):
            listing.price = int(price)
        listing.currency = "AED"

        area = data.get("area")
        if isinstance(area, (int, float)) and area > 0:
            listing.area_sqft = float(area)
            listing.area_sqm = round(float(area) * SQFT_TO_SQM, 2)

        rooms = data.get("rooms")
        if isinstance(rooms, int) and rooms > 0:
            listing.rooms = rooms

        baths = data.get("baths")
        if isinstance(baths, int) and baths > 0:
            listing.bathrooms = baths

        listing.address = _format_address(data.get("location"))

        agency = data.get("agency")
        if isinstance(agency, dict):
            listing.broker_agency = _as_str(agency.get("name"))

        listing.broker_name = _as_str(data.get("contactName"))

        phone = data.get("phoneNumber")
        if isinstance(phone, dict):
            listing.broker_phone = _as_str(
                phone.get("mobile") or phone.get("phone") or phone.get("whatsapp")
            )
        elif isinstance(phone, str):
            listing.broker_phone = phone.strip()

        listing.photo_urls = _collect_photo_urls(data)

        logger.info(
            "Bayut API parsed id=%s title=%r address=%r price=%s rooms=%s baths=%s area_sqm=%s photos=%d",
            property_id,
            listing.title[:60], listing.address[:60],
            listing.price, listing.rooms, listing.bathrooms, listing.area_sqm,
            len(listing.photo_urls),
        )
        return listing


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_property_type(data: dict) -> str:
    """Return the most specific category name (e.g. ``Apartment``, ``Plot``)."""
    category = data.get("category")
    if not isinstance(category, list):
        return ""
    items = [c for c in category if isinstance(c, dict)]
    items.sort(key=lambda c: c.get("level", -1), reverse=True)  # deepest first
    for c in items:
        name = c.get("nameSingular") or c.get("name")
        if name:
            return _as_str(name)
    return ""


def _extract_features(data: dict) -> list[str]:
    """Flatten Bayut amenities into a plain list of feature names."""
    amenities = data.get("amenities")
    if not isinstance(amenities, list):
        return []
    features: list[str] = []
    for group in amenities:
        if not isinstance(group, dict):
            continue
        items = group.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str) and item.strip():
                    features.append(item.strip())
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("title")
                    if isinstance(name, str) and name.strip():
                        features.append(name.strip())
    # Dedup, keep order
    seen: set[str] = set()
    deduped: list[str] = []
    for f in features:
        if f not in seen:
            seen.add(f)
            deduped.append(f)
    return deduped


def _format_address(location: Any) -> str:
    """Build address from the location hierarchy, most-specific first.

    location = [
        {"level": 0, "name": "UAE"},
        {"level": 1, "name": "Dubai"},
        {"level": 2, "name": "Palm Jumeirah"},
        {"level": 3, "name": "The Crescent"},
    ]
    → "The Crescent, Palm Jumeirah, Dubai, UAE"
    """
    if not isinstance(location, list):
        return ""

    items = [
        loc for loc in location
        if isinstance(loc, dict) and loc.get("name")
    ]
    # Deepest level first; if level missing, treat as last.
    items.sort(key=lambda loc: loc.get("level", 999), reverse=True)

    seen: set[str] = set()
    parts: list[str] = []
    for loc in items:
        name = _as_str(loc.get("name"))
        if name and name not in seen:
            seen.add(name)
            parts.append(name)
    return ", ".join(parts)


def _collect_photo_urls(data: dict) -> list[str]:
    urls: list[str] = []

    photos = data.get("photos")
    if isinstance(photos, list):
        items = sorted(
            [p for p in photos if isinstance(p, dict)],
            key=lambda p: p.get("orderIndex", 999),
        )
        for p in items:
            url = _resolve_photo_url(p)
            if url:
                urls.append(url)

    if not urls:
        cover = data.get("coverPhoto")
        url = _resolve_photo_url(cover)
        if url:
            urls.append(url)

    # De-dup, preserve order
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def _resolve_photo_url(photo: Any) -> str | None:
    """Some listings return ready ``url``, others only ``id`` + ``externalID``.

    For id-only photos we build a thumbnail URL by template:
    https://images.bayut.com/thumbnails/{id}-800x600.jpeg
    """
    if not isinstance(photo, dict):
        return None

    url = photo.get("url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return url

    photo_id = photo.get("id") or photo.get("externalID")
    if photo_id is None:
        return None
    template = getattr(
        settings,
        "BAYUT_PHOTO_URL_TEMPLATE",
        "https://images.bayut.com/thumbnails/{id}-800x600.jpeg",
    )
    return template.format(id=str(photo_id).strip())
