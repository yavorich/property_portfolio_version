import json
import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .base import ParsedListing

logger = logging.getLogger(__name__)

NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

SQFT_TO_SQM = 0.092903


class PropertyFinderParser:
    """Property Finder listing parser.

    PF is a Next.js app — primary extraction target is the ``__NEXT_DATA__``
    JSON blob; JSON-LD and og: tags are used as fallbacks.
    """

    SOURCE = "property_finder"

    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def parse(self, url: str) -> ParsedListing:
        response = await self.http.get(url, headers=DEFAULT_HEADERS, follow_redirects=True)
        response.raise_for_status()
        html = response.text
        final_url = str(response.url)

        listing = ParsedListing(source=self.SOURCE, source_url=final_url)
        soup = BeautifulSoup(html, "html.parser")

        next_data = self._extract_next_data(html)
        if next_data:
            listing.raw_data = next_data
            prop = self._find_property_node(next_data)
            if prop:
                self._fill_from_next_data(listing, prop)
            else:
                logger.warning("PF: __NEXT_DATA__ parsed but no property node")
        else:
            logger.warning("PF: __NEXT_DATA__ not found")

        self._fill_from_jsonld(listing, soup)
        self._fill_from_meta(listing, soup)

        logger.info(
            "PF extracted: title=%r address=%r price=%s photos=%d",
            listing.title[:60], listing.address[:60],
            listing.price, len(listing.photo_urls),
        )

        if not listing.title and not listing.photo_urls and not listing.price:
            raise ValueError(
                "Failed to extract Property Finder listing — page structure "
                "changed or request was blocked."
            )
        return listing

    def _extract_next_data(self, html: str) -> dict | None:
        match = NEXT_DATA_RE.search(html)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse __NEXT_DATA__ JSON: %s", exc)
            return None

    def _find_property_node(self, data: dict) -> dict:
        page_props = data.get("props", {}).get("pageProps", {})
        # PF uses several keys depending on page type
        for key in ("propertyResult", "property", "listingDetail", "data", "initialState"):
            node = page_props.get(key)
            if isinstance(node, dict) and node:
                inner = node.get("property") or node.get("listing")
                if isinstance(inner, dict) and inner:
                    return inner
                return node
        for value in page_props.values():
            if isinstance(value, dict) and {"title", "price"} & value.keys():
                return value
        return {}

    def _fill_from_next_data(self, listing: ParsedListing, p: dict) -> None:
        listing.title = _as_str(p.get("title")) or listing.title

        listing.description = _as_str(
            p.get("description") or p.get("description_text") or p.get("descriptionText")
        ) or listing.description

        price = p.get("price")
        if isinstance(price, dict):
            price = price.get("value") or price.get("amount")
        if isinstance(price, (int, float)):
            listing.price = int(price)
        elif isinstance(price, str):
            digits = re.sub(r"[^\d]", "", price)
            if digits:
                listing.price = int(digits)

        currency = p.get("currency") or _dig(p, "price", "currency")
        if currency:
            listing.currency = _as_str(currency)

        size = p.get("size")
        if isinstance(size, dict):
            value = size.get("value")
            unit = (size.get("unit") or "").lower()
            if isinstance(value, (int, float)):
                if unit in ("sqft", "ft²", "ft"):
                    listing.area_sqft = float(value)
                    listing.area_sqm = round(float(value) * SQFT_TO_SQM, 2)
                else:
                    listing.area_sqm = float(value)
                    listing.area_sqft = round(float(value) / SQFT_TO_SQM, 2)
        elif isinstance(size, (int, float)):
            listing.area_sqft = float(size)
            listing.area_sqm = round(float(size) * SQFT_TO_SQM, 2)

        for rooms_key in ("bedrooms", "bedroom", "beds", "rooms"):
            value = p.get(rooms_key)
            if isinstance(value, int):
                listing.rooms = value
                break
            if isinstance(value, str) and value.isdigit():
                listing.rooms = int(value)
                break

        for baths_key in ("bathrooms", "baths"):
            value = p.get(baths_key)
            if isinstance(value, int):
                listing.bathrooms = value
                break

        location = p.get("location") or p.get("locationHierarchy")
        if isinstance(location, list) and location:
            listing.address = ", ".join(
                _as_str(loc.get("name") or loc.get("title"))
                for loc in location
                if isinstance(loc, dict) and (loc.get("name") or loc.get("title"))
            )
        elif isinstance(location, dict):
            listing.address = _as_str(
                location.get("full_name") or location.get("name") or location.get("title")
            )

        images = p.get("images") or p.get("photos") or p.get("media")
        urls: list[str] = []
        if isinstance(images, dict):
            images = images.get("photos") or images.get("items") or []
        if isinstance(images, list):
            for img in images:
                if isinstance(img, dict):
                    candidate = (
                        img.get("full")
                        or img.get("url")
                        or img.get("large")
                        or img.get("src")
                    )
                    if candidate:
                        urls.append(candidate)
                elif isinstance(img, str):
                    urls.append(img)
        listing.photo_urls = urls

        broker = p.get("broker") or p.get("agent") or {}
        if isinstance(broker, dict):
            listing.broker_name = _as_str(broker.get("name"))
            contact = broker.get("contact") or broker
            if isinstance(contact, dict):
                listing.broker_phone = _as_str(
                    contact.get("phone")
                    or contact.get("mobile")
                    or contact.get("whatsapp")
                )
                listing.broker_email = _as_str(contact.get("email"))

        agency = p.get("agency") or p.get("brokerage")
        if isinstance(agency, dict):
            listing.broker_agency = _as_str(agency.get("name"))

    def _fill_from_meta(self, listing: ParsedListing, soup: BeautifulSoup) -> None:
        if not listing.title:
            tag = soup.find("meta", property="og:title") or soup.find("title")
            if tag:
                content = tag.get("content") if tag.name == "meta" else tag.text
                if content:
                    listing.title = content.strip()

        if not listing.description:
            tag = soup.find("meta", property="og:description") or soup.find(
                "meta", attrs={"name": "description"}
            )
            if tag and tag.get("content"):
                listing.description = tag["content"].strip()

        if not listing.photo_urls:
            tags = soup.find_all("meta", property="og:image")
            listing.photo_urls = [t["content"] for t in tags if t.get("content")]

    def _fill_from_jsonld(self, listing: ParsedListing, soup: BeautifulSoup) -> None:
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                if not listing.title and (name := item.get("name")):
                    listing.title = _as_str(name)
                if not listing.description and (desc := item.get("description")):
                    listing.description = _as_str(desc)
                if not listing.address:
                    addr = item.get("address")
                    if isinstance(addr, dict):
                        parts = [
                            addr.get("streetAddress"),
                            addr.get("addressLocality"),
                            addr.get("addressRegion"),
                            addr.get("addressCountry"),
                        ]
                        listing.address = ", ".join(p for p in parts if p)
                    elif isinstance(addr, str):
                        listing.address = addr
                if listing.price is None and (offers := item.get("offers")):
                    offer = offers[0] if isinstance(offers, list) and offers else offers
                    if isinstance(offer, dict):
                        try:
                            price = int(float(offer.get("price", 0)))
                            listing.price = price or None
                        except (TypeError, ValueError):
                            pass
                        if cur := offer.get("priceCurrency"):
                            listing.currency = _as_str(cur)
                if not listing.photo_urls and (image := item.get("image")):
                    if isinstance(image, list):
                        listing.photo_urls = [i for i in image if isinstance(i, str)]
                    elif isinstance(image, str):
                        listing.photo_urls = [image]


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _dig(obj: Any, *keys: str) -> Any:
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return None
    return obj
