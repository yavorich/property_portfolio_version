import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlparse

import httpx
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.account.models import User
from apps.listings.models import Listing, ListingPhoto
from apps.listings.parsers import ParsedListing, get_parser
from telegram_bot.proxies import load_proxies

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str], Awaitable[None]]

PAGE_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
PHOTO_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


async def process_url(url: str, user: User, on_status: StatusCallback) -> Listing:
    """Parse a listing URL, persist its data, and download all photos locally."""

    proxies = load_proxies()
    http, proxy = await _open_working_client(url, proxies)
    try:
        logger.info("Processing %s via proxy=%s", url, proxy or "direct")

        await on_status("📥 Скачиваю страницу листинга…")
        parser = get_parser(url, http)
        parsed = await parser.parse(url)

        await on_status("💾 Сохраняю данные объекта…")
        listing = await _save_listing(user, parsed)

        if parsed.photo_urls:
            await on_status(f"🖼 Скачиваю фото ({len(parsed.photo_urls)} шт.)…")
            await _download_photos(listing, parsed.photo_urls, http)

        listing.status = Listing.Status.PARSED
        await listing.asave(update_fields=["status", "updated_at"])
        return listing
    finally:
        await http.aclose()


async def _open_working_client(
    test_url: str, proxies: list[str | None]
) -> tuple[httpx.AsyncClient, str | None]:
    """Open an httpx client with the first proxy that can reach test_url."""

    last_error: Exception | None = None
    for proxy in proxies:
        client = _build_client(proxy, PAGE_TIMEOUT)
        try:
            response = await client.head(
                test_url, follow_redirects=True, timeout=httpx.Timeout(10.0)
            )
            if response.status_code < 500:
                return client, proxy
            await client.aclose()
        except Exception as exc:
            last_error = exc
            logger.warning("Proxy %s unreachable for %s: %s", proxy or "direct", test_url, exc)
            await client.aclose()
    raise RuntimeError(f"No working proxy for {test_url}: {last_error!r}")


def _build_client(proxy: str | None, timeout: httpx.Timeout) -> httpx.AsyncClient:
    kwargs: dict = {"timeout": timeout, "follow_redirects": True}
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


async def _save_listing(user: User, parsed: ParsedListing) -> Listing:
    return await Listing.objects.acreate(
        user=user,
        source=parsed.source,
        source_url=parsed.source_url,
        status=Listing.Status.PARSING,
        title=parsed.title,
        address=parsed.address,
        description=parsed.description,
        price=parsed.price,
        currency=parsed.currency,
        area_sqft=parsed.area_sqft,
        area_sqm=parsed.area_sqm,
        rooms=parsed.rooms,
        bathrooms=parsed.bathrooms,
        floor=parsed.floor,
        broker_name=parsed.broker_name,
        broker_phone=parsed.broker_phone,
        broker_email=parsed.broker_email,
        broker_agency=parsed.broker_agency,
        raw_data=parsed.raw_data,
    )


async def _download_photos(
    listing: Listing, urls: list[str], http: httpx.AsyncClient
) -> None:
    listing.status = Listing.Status.DOWNLOADING
    await listing.asave(update_fields=["status", "updated_at"])

    for idx, url in enumerate(urls):
        try:
            response = await http.get(url, timeout=PHOTO_TIMEOUT)
            response.raise_for_status()
            filename = _guess_filename(url, response.headers.get("content-type"), idx)
            photo = ListingPhoto(listing=listing, index=idx, source_url=url)
            await asyncio.to_thread(
                photo.original.save, filename, ContentFile(response.content), False
            )
            photo.downloaded_at = timezone.now()
            await photo.asave()
        except Exception:
            logger.exception("Failed to download photo #%d (%s)", idx, url)


def _guess_filename(url: str, content_type: str | None, idx: int) -> str:
    ext = ""
    path_suffix = Path(urlparse(url).path).suffix.lower()
    if path_suffix and len(path_suffix) <= 6:
        ext = path_suffix
    elif content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            ext = guessed
    if not ext:
        ext = ".jpg"
    return f"{idx:04d}{ext}"
