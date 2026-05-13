import logging
import re
from typing import Any

import httpx
from django.conf import settings

from .base import ParsedListing

logger = logging.getLogger(__name__)

# Property Finder URLs look like:
#   https://www.propertyfinder.ae/en/plp/rent/apartment-for-rent-...-75999622.html
# The trailing -<digits>.html is the property id.
PROPERTY_ID_RE = re.compile(r"-(\d+)\.html", re.IGNORECASE)

SQFT_TO_SQM = 0.092903


class PropertyFinderParser:
    """Property Finder parser backed by the RapidAPI ``propertyfinder-uae-data`` API."""

    SOURCE = "property_finder"

    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def parse(self, url: str) -> ParsedListing:
        api_key = getattr(settings, "PROPERTYFINDER_API_KEY", "")
        if not api_key:
            raise RuntimeError("PROPERTYFINDER_API_KEY is not configured")

        property_id = self._extract_property_id(url)
        api_url = (
            f"{settings.PROPERTYFINDER_API_BASE_URL.rstrip('/')}/property-details"
        )
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": settings.PROPERTYFINDER_API_HOST,
            "Accept": "application/json",
        }

        response = await self.http.get(
            api_url,
            params={"property_id": property_id},
            headers=headers,
        )
        if response.status_code != 200:
            detail = response.text[:500]
            logger.error(
                "PF API failed: status=%s url=%s body=%s",
                response.status_code, api_url, detail,
            )
            raise RuntimeError(
                f"Property Finder API returned {response.status_code}: {detail}"
            )

        data = response.json()
        return self._to_listing(url, property_id, data)

    @staticmethod
    def _extract_property_id(url: str) -> str:
        match = PROPERTY_ID_RE.search(url)
        if not match:
            raise ValueError(
                "Cannot extract Property Finder property ID from URL — expected "
                "'-<id>.html' suffix"
            )
        return match.group(1)

    def _to_listing(self, source_url: str, property_id: str, data: dict) -> ParsedListing:
        # Some vendors wrap the payload in {"data": {...}} or {"property": {...}}.
        body = _unwrap(data)

        logger.info(
            "PF API outer keys=%s, body keys=%s, body sample=%s",
            list(data.keys()) if isinstance(data, dict) else type(data).__name__,
            list(body.keys()) if isinstance(body, dict) else type(body).__name__,
            _truncate_repr(body, limit=600),
        )

        listing = ParsedListing(
            source=self.SOURCE,
            source_url=_first_str(body.get("share_url"), body.get("url")) or source_url,
            raw_data=data,
        )

        listing.title = _first_str(
            body.get("title"), body.get("name"), body.get("listing_title")
        )
        listing.description = _first_str(
            body.get("description"),
            body.get("description_text"),
            body.get("descriptionText"),
            body.get("description_en"),
        )

        # Price
        price_val = body.get("price")
        if isinstance(price_val, dict):
            currency = price_val.get("currency")
            if currency:
                listing.currency = _as_str(currency)
            price_val = (
                price_val.get("value")
                or price_val.get("amount")
                or price_val.get("price")
            )
        if isinstance(price_val, (int, float)):
            listing.price = int(price_val)
        elif isinstance(price_val, str):
            digits = re.sub(r"[^\d]", "", price_val)
            if digits:
                listing.price = int(digits)

        # Area
        size = body.get("size") or body.get("area")
        if isinstance(size, dict):
            value = size.get("value") or size.get("built_up") or size.get("size")
            unit = (size.get("unit") or "").lower()
            if isinstance(value, (int, float)):
                _fill_area(listing, float(value), unit)
        elif isinstance(size, (int, float)):
            _fill_area(listing, float(size), "")

        # Rooms / baths
        for key in ("bedrooms", "bedroom", "beds", "rooms"):
            v = body.get(key)
            if isinstance(v, int):
                listing.rooms = v
                break
            if isinstance(v, str) and v.isdigit():
                listing.rooms = int(v)
                break
        for key in ("bathrooms", "baths"):
            v = body.get(key)
            if isinstance(v, int):
                listing.bathrooms = v
                break
            if isinstance(v, str) and v.isdigit():
                listing.bathrooms = int(v)
                break

        # Address
        listing.address = _format_address(body)

        # Photos
        listing.photo_urls = _collect_photo_urls(body)

        # Broker / agent / agency
        broker = body.get("broker") or body.get("agent") or {}
        if isinstance(broker, dict):
            listing.broker_name = _as_str(broker.get("name"))
            contact = broker.get("contact") or broker
            if isinstance(contact, dict):
                listing.broker_phone = _first_str(
                    contact.get("phone"),
                    contact.get("mobile"),
                    contact.get("whatsapp"),
                )
                listing.broker_email = _as_str(contact.get("email"))

        agency = body.get("agency") or body.get("brokerage") or body.get("broker_company")
        if isinstance(agency, dict):
            listing.broker_agency = _as_str(agency.get("name"))
        elif isinstance(agency, str):
            listing.broker_agency = agency.strip()

        logger.info(
            "PF API parsed id=%s title=%r address=%r price=%s photos=%d",
            property_id, listing.title[:60], listing.address[:60],
            listing.price, len(listing.photo_urls),
        )
        return listing


def _unwrap(data: dict) -> dict:
    """Return the inner property object regardless of common wrappers."""
    if not isinstance(data, dict):
        return {}
    for key in ("data", "property", "listing", "result"):
        inner = data.get(key)
        if isinstance(inner, dict) and inner:
            return inner
    return data


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _truncate_repr(value: Any, limit: int = 600) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + "…"


def _first_str(*values: Any) -> str:
    for value in values:
        s = _as_str(value)
        if s:
            return s
    return ""


def _fill_area(listing: ParsedListing, value: float, unit: str) -> None:
    unit = (unit or "").lower()
    if unit in ("sqft", "ft²", "ft", "square_feet"):
        listing.area_sqft = value
        listing.area_sqm = round(value * SQFT_TO_SQM, 2)
    elif unit in ("sqm", "m²", "m2", "square_meters"):
        listing.area_sqm = value
        listing.area_sqft = round(value / SQFT_TO_SQM, 2)
    else:
        # Heuristic: PF usually quotes sqft; small numbers → sqm
        if value < 500:
            listing.area_sqm = value
            listing.area_sqft = round(value / SQFT_TO_SQM, 2)
        else:
            listing.area_sqft = value
            listing.area_sqm = round(value * SQFT_TO_SQM, 2)


def _format_address(body: dict) -> str:
    # Try a flat string field first
    for key in ("address", "location_name", "location_string"):
        v = body.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # Then a list / hierarchy
    location = body.get("location") or body.get("locationHierarchy") or body.get("breadcrumbs")
    if isinstance(location, list):
        parts = [
            _as_str(loc.get("name") or loc.get("title"))
            for loc in location
            if isinstance(loc, dict) and (loc.get("name") or loc.get("title"))
        ]
        if parts:
            return ", ".join(dict.fromkeys(parts))
    elif isinstance(location, dict):
        return _first_str(
            location.get("full_name"),
            location.get("name"),
            location.get("title"),
        )
    return ""


def _collect_photo_urls(body: dict) -> list[str]:
    candidates = (
        body.get("images")
        or body.get("photos")
        or body.get("media")
        or body.get("gallery")
        or []
    )

    if isinstance(candidates, dict):
        candidates = (
            candidates.get("photos")
            or candidates.get("items")
            or candidates.get("images")
            or []
        )

    if not isinstance(candidates, list):
        return []

    urls: list[str] = []
    for item in candidates:
        if isinstance(item, str) and item.startswith(("http://", "https://")):
            urls.append(item)
        elif isinstance(item, dict):
            candidate = (
                item.get("full")
                or item.get("url")
                or item.get("large")
                or item.get("original")
                or item.get("src")
                or item.get("photo")
                or item.get("link")
            )
            if candidate and isinstance(candidate, str):
                urls.append(candidate)

    # De-dup, preserve order
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped
