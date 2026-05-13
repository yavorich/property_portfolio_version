import asyncio
import logging
from typing import Awaitable, Callable

from django.core.files.base import ContentFile

from apps.listings.models import Listing, ListingPhoto
from apps.watermark.services import clean_image_dewatermark

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str], Awaitable[None]]


async def remove_watermarks(
    listing: Listing,
    on_status: StatusCallback,
    *,
    limit: int | None = None,
) -> int:
    """Run each downloaded photo through Dewatermark.ai and store as ``processed``.

    Returns the number of successfully processed photos. ``limit`` caps the
    number of photos processed (cheapest way to control API quota — we only
    need the photos that actually go into the PDF).
    """
    photos: list[ListingPhoto] = []
    async for photo in listing.photos.order_by("index"):
        if not photo.original:
            continue
        photos.append(photo)
        if limit and len(photos) >= limit:
            break
    total = len(photos)
    if not total:
        return 0

    processed = 0
    for i, photo in enumerate(photos, start=1):
        await on_status(f"🧹 Удаляю водяной знак ({i}/{total})…")
        try:
            image_bytes = await asyncio.to_thread(_read_original, photo)
            cleaned = await clean_image_dewatermark(image_bytes)
            filename = f"{photo.index:04d}.png"
            await asyncio.to_thread(
                photo.processed.save, filename, ContentFile(cleaned), False
            )
            await photo.asave(update_fields=["processed"])
            processed += 1
        except Exception:
            logger.exception(
                "Failed to remove watermark for listing=%s photo_index=%s",
                listing.id, photo.index,
            )
    return processed


def _read_original(photo: ListingPhoto) -> bytes:
    with photo.original.open("rb") as fh:
        return fh.read()
