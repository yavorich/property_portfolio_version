import logging
import re
from typing import Any

import httpx
from django.conf import settings

from .base import ParsedListing

logger = logging.getLogger(__name__)

# Bayut listing URLs look like:
#   https://www.bayut.com/property/details-13898698.html
#   https://www.bayut.com/ru/property/details-13898698.html
#   https://www.bayut.com/en-ae/property/details-13898698.html
PROPERTY_ID_RE = re.compile(r"/details-(\d+)", re.IGNORECASE)

SQFT_TO_SQM = 0.092903


class BayutParser:
    """Bayut listing parser backed by the RapidAPI ``uae-real-estate2`` service.

    Endpoint: ``GET /property/{property_id}`` on the configured base URL,
    with ``X-RapidAPI-Key`` and ``X-RapidAPI-Host`` headers.
    """

    SOURCE = "bayut"

    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def parse(self, url: str) -> ParsedListing:
        api_key = getattr(settings, "BAYUT_API_KEY", "")
        if not api_key:
            raise RuntimeError("BAYUT_API_KEY is not configured")

        property_id = self._extract_property_id(url)
        api_url = f"{settings.BAYUT_API_BASE_URL.rstrip('/')}/property/{property_id}"
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": settings.BAYUT_API_HOST,
            "Accept": "application/json",
        }

        response = await self.http.get(api_url, headers=headers)
        if response.status_code != 200:
            detail = response.text[:500]
            logger.error(
                "Bayut API failed: status=%s url=%s body=%s",
                response.status_code, api_url, detail,
            )
            raise RuntimeError(
                f"Bayut API returned {response.status_code}: {detail}"
            )

        data = response.json()
        return self._to_listing(url, property_id, data)

    @staticmethod
    def _extract_property_id(url: str) -> str:
        match = PROPERTY_ID_RE.search(url)
        if not match:
            raise ValueError(
                "Cannot extract Bayut property ID from URL — expected "
                "'/details-<id>' segment"
            )
        return match.group(1)

    def _to_listing(self, source_url: str, property_id: str, data: dict) -> ParsedListing:
        listing = ParsedListing(
            source=self.SOURCE,
            source_url=_as_str(_dig(data, "meta", "url")) or source_url,
            raw_data=data,
        )

        listing.title = _as_str(data.get("title"))
        listing.description = _as_str(data.get("description"))

        price = data.get("price")
        if isinstance(price, (int, float)):
            listing.price = int(price)
        listing.currency = "AED"

        area = data.get("area") or {}
        if isinstance(area, dict):
            built_up = area.get("built_up")
            unit = (area.get("unit") or "").lower()
            if isinstance(built_up, (int, float)):
                if unit == "sqft":
                    listing.area_sqft = float(built_up)
                    listing.area_sqm = round(float(built_up) * SQFT_TO_SQM, 2)
                elif unit in ("sqm", "m2", "m²"):
                    listing.area_sqm = float(built_up)
                    listing.area_sqft = round(float(built_up) / SQFT_TO_SQM, 2)
                else:
                    listing.area_sqft = float(built_up)
                    listing.area_sqm = round(float(built_up) * SQFT_TO_SQM, 2)

        details = data.get("details") or {}
        if isinstance(details, dict):
            if isinstance(details.get("bedrooms"), int):
                listing.rooms = details["bedrooms"]
            if isinstance(details.get("bathrooms"), int):
                listing.bathrooms = details["bathrooms"]

        listing.address = _format_address(data.get("location") or {})

        agency = data.get("agency") or {}
        if isinstance(agency, dict):
            listing.broker_agency = _as_str(agency.get("name"))

        agent = data.get("agent") or {}
        if isinstance(agent, dict):
            listing.broker_name = _as_str(agent.get("name"))
            contact = agent.get("contact") or {}
            if isinstance(contact, dict):
                listing.broker_phone = _as_str(
                    contact.get("mobile")
                    or contact.get("phone")
                    or contact.get("whatsapp")
                )

        listing.photo_urls = _collect_photo_urls(data, property_id)

        logger.info(
            "Bayut API parsed id=%s title=%r address=%r price=%s photos=%d",
            property_id, listing.title[:60], listing.address[:60],
            listing.price, len(listing.photo_urls),
        )
        return listing


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _truncate_repr(value: Any, limit: int = 200) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + "…"


def _dig(obj: Any, *keys: str) -> Any:
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return None
    return obj


def _collect_photo_urls(data: dict, property_id: str) -> list[str]:
    media = data.get("media")
    if not isinstance(media, dict):
        logger.warning("Bayut id=%s: no media in response", property_id)
        return []

    logger.info(
        "Bayut id=%s media keys=%s photo_count=%s cover=%s",
        property_id,
        list(media.keys()),
        media.get("photo_count"),
        bool(media.get("cover_photo")),
    )

    urls: list[str] = []
    photos = media.get("photos")
    if isinstance(photos, list) and photos:
        sample = photos[0]
        sample_keys = list(sample.keys()) if isinstance(sample, dict) else type(sample).__name__
        logger.info(
            "Bayut id=%s photos[0] type=%s sample=%r keys=%s",
            property_id, type(photos[0]).__name__, _truncate_repr(sample), sample_keys,
        )
        for item in photos:
            if isinstance(item, str) and item:
                urls.append(item)
            elif isinstance(item, dict):
                candidate = (
                    item.get("url")
                    or item.get("full")
                    or item.get("large")
                    or item.get("original")
                    or item.get("main")
                    or item.get("src")
                    or item.get("photo")
                    or item.get("link")
                    or item.get("path")
                )
                if candidate:
                    urls.append(candidate)
                else:
                    # Try to assemble from id/key pieces (Bayut S3 pattern)
                    photo_id = item.get("id") or item.get("photo_id") or item.get("key")
                    if photo_id:
                        urls.append(
                            f"https://images.bayut.com/thumbnails/{photo_id}-800x600.jpeg"
                        )

    if not urls and (cover := media.get("cover_photo")):
        if isinstance(cover, str) and cover:
            urls.append(cover)

    # De-dup, preserve order
    seen: set[str] = set()
    deduped = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def _format_address(location: dict) -> str:
    if not isinstance(location, dict):
        return ""
    parts: list[str] = []
    for key in ("cluster", "sub_community", "community", "city", "country"):
        node = location.get(key)
        if isinstance(node, dict) and node.get("name"):
            parts.append(_as_str(node["name"]))
    return ", ".join(dict.fromkeys(p for p in parts if p))  # de-dup, preserve order
