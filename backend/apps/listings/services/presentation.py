import asyncio
import logging
import tempfile
from pathlib import Path

import pdfkit
from django.core.files import File
from django.template.loader import render_to_string

from apps.listings.models import Listing, ListingPhoto

logger = logging.getLogger(__name__)

PRESENTATION_PHOTO_COUNT = 4  # 1 hero + 3 thumbnails on the cover page

PDFKIT_OPTIONS = {
    "enable-local-file-access": "",
    "page-size": "A4",
    "encoding": "UTF-8",
    "margin-top": "12mm",
    "margin-right": "12mm",
    "margin-bottom": "12mm",
    "margin-left": "12mm",
    "quiet": "",
}


async def generate_pdf(listing: Listing) -> Path | None:
    """Render the listing's PDF presentation and attach it to ``listing.presentation``."""
    return await asyncio.to_thread(_generate_sync, listing)


def _generate_sync(listing: Listing) -> Path | None:
    photos = list(listing.photos.order_by("index"))
    image_urls = [_photo_file_url(p) for p in photos]
    image_urls = [u for u in image_urls if u]

    hero_url = image_urls[0] if image_urls else None
    thumb_urls = image_urls[1:4]  # up to 3 thumbnails

    placeholder_thumbs = range(max(0, 3 - len(thumb_urls))) if thumb_urls else range(0)

    address_parts = [
        p.strip() for p in (listing.address or "").split(",") if p.strip()
    ]

    context = {
        "listing": listing,
        "hero_url": hero_url,
        "thumb_urls": thumb_urls,
        "placeholder_thumbs": placeholder_thumbs,
        "price_formatted": _format_price(listing),
        "specs_line": _format_specs(listing),
        "address_parts": address_parts,
    }

    html = render_to_string("listings/listing_pdf.html", context)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        pdfkit.from_string(html, str(tmp_path), options=PDFKIT_OPTIONS)
        with tmp_path.open("rb") as fh:
            filename = f"{listing.reference_code or listing.uuid}.pdf"
            listing.presentation.save(filename, File(fh), save=False)
        listing.save(update_fields=["presentation", "updated_at"])
        logger.info("Listing %s PDF saved to %s", listing.id, listing.presentation.name)
        return Path(listing.presentation.path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _photo_file_url(photo: ListingPhoto) -> str | None:
    """Prefer processed (watermark-removed) image, fall back to original."""
    field = photo.processed if photo.processed else photo.original
    if not field:
        return None
    try:
        return f"file://{Path(field.path).as_posix()}"
    except (ValueError, NotImplementedError):
        return None


def _format_price(listing: Listing) -> str:
    if listing.price is None:
        return ""
    currency = listing.currency or "AED"
    formatted = f"{listing.price:,}".replace(",", ",")
    return f"{currency} {formatted}"


def _format_specs(listing: Listing) -> str:
    parts: list[str] = []
    if listing.property_type:
        parts.append(listing.property_type)
    if listing.rooms is not None:
        parts.append(f"{listing.rooms} Beds")
    if listing.bathrooms is not None:
        parts.append(f"{listing.bathrooms} Baths")
    if listing.area_sqft:
        parts.append(f"{int(round(listing.area_sqft))} sqft")
    elif listing.area_sqm:
        parts.append(f"{listing.area_sqm:g} m²")
    return " • ".join(parts)


