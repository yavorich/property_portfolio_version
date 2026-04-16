import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils import timezone

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
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Chromium";v="124", "Not-A.Brand";v="99", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

SQFT_TO_SQM = 0.092903


class BayutParser:
    """Parses a Bayut.com property listing page.

    Primary target: ``__NEXT_DATA__`` Next.js JSON blob. Fallbacks: JSON-LD
    scripts, og: meta tags. On total extraction failure the HTML is dumped
    to ``MEDIA_ROOT/debug/bayut/`` for offline inspection.
    """

    SOURCE = "bayut"

    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def parse(self, url: str) -> ParsedListing:
        response = await self.http.get(url, headers=DEFAULT_HEADERS, follow_redirects=True)
        response.raise_for_status()
        html = response.text
        final_url = str(response.url)

        logger.info(
            "Bayut fetch: status=%s final_url=%s bytes=%d",
            response.status_code, final_url, len(html),
        )

        listing = ParsedListing(source=self.SOURCE, source_url=final_url)
        soup = BeautifulSoup(html, "html.parser")

        next_data = self._extract_next_data(html)
        if next_data:
            listing.raw_data = next_data
            prop = self._find_property_node(next_data)
            if prop:
                logger.info("Bayut: property node keys=%s", list(prop.keys())[:20])
                self._fill_from_next_data(listing, prop)
            else:
                logger.warning("Bayut: __NEXT_DATA__ parsed but no property node found")
        else:
            logger.warning("Bayut: __NEXT_DATA__ script not found")

        self._fill_from_jsonld(listing, soup)
        self._fill_from_meta(listing, soup)

        logger.info(
            "Bayut extracted: title=%r address=%r price=%s photos=%d",
            listing.title[:60], listing.address[:60], listing.price, len(listing.photo_urls),
        )

        if not listing.title and not listing.photo_urls and not listing.price:
            dump_path = _dump_html(url, html)
            raise ValueError(
                "Failed to extract Bayut listing — page likely bot-blocked or "
                f"structure changed. HTML dumped to {dump_path}"
            )
        return listing

    def _extract_next_data(self, html: str) -> dict | None:
        match = NEXT_DATA_RE.search(html)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse __NEXT_DATA__ as JSON: %s", exc)
            return None

    def _find_property_node(self, data: dict) -> dict:
        page_props = data.get("props", {}).get("pageProps", {})
        for key in ("property", "propertyData", "data", "listing", "initialData"):
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
            p.get("description") or p.get("description_l1") or p.get("description_l2")
        ) or listing.description

        if (price := p.get("price")) is not None:
            try:
                listing.price = int(price)
            except (TypeError, ValueError):
                pass

        if (area := p.get("area")) is not None:
            try:
                listing.area_sqft = float(area)
                listing.area_sqm = round(float(area) * SQFT_TO_SQM, 2)
            except (TypeError, ValueError):
                pass

        if isinstance(p.get("rooms"), int):
            listing.rooms = p["rooms"]
        if isinstance(p.get("baths"), int):
            listing.bathrooms = p["baths"]
        if (floor := p.get("floor") or p.get("floorNumber")) is not None:
            listing.floor = _as_str(floor)

        location = p.get("location")
        if isinstance(location, list) and location:
            listing.address = ", ".join(
                _as_str(loc.get("name"))
                for loc in location
                if isinstance(loc, dict) and loc.get("name")
            )
        elif isinstance(location, dict):
            listing.address = _as_str(location.get("name"))

        listing.photo_urls = _collect_photo_urls(p)

        for name_key in ("contactName", "contact_name", "ownerName"):
            if p.get(name_key):
                listing.broker_name = _as_str(p[name_key])
                break

        phone = p.get("phoneNumber") or p.get("phone")
        if isinstance(phone, dict):
            listing.broker_phone = _as_str(
                phone.get("mobile") or phone.get("whatsapp") or phone.get("phone")
            )
        elif phone:
            listing.broker_phone = _as_str(phone)

        if email := p.get("contactEmail") or p.get("email"):
            listing.broker_email = _as_str(email)

        agency = p.get("agency")
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


def _collect_photo_urls(prop: dict) -> list[str]:
    candidates = prop.get("photos") or prop.get("images") or prop.get("gallery") or []
    if not isinstance(candidates, list):
        return []
    urls: list[str] = []
    for photo in candidates:
        if isinstance(photo, dict):
            url = (
                photo.get("url")
                or photo.get("large")
                or photo.get("original")
                or photo.get("main")
                or photo.get("src")
            )
            if url:
                urls.append(url)
        elif isinstance(photo, str):
            urls.append(photo)
    return urls


def _dump_html(url: str, html: str) -> Path:
    debug_dir = Path(settings.MEDIA_ROOT) / "debug" / "bayut"
    debug_dir.mkdir(parents=True, exist_ok=True)
    stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    path = debug_dir / f"{stamp}-{digest}.html"
    try:
        path.write_text(html, encoding="utf-8")
    except OSError:
        logger.exception("Failed to write HTML dump to %s", path)
    return path
