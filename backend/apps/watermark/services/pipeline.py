import asyncio
import logging

from django.conf import settings

from .detector import TextBox, detect_watermark_boxes
from .dewatermark import erase_watermark as dewatermark_erase
from .mask import build_default_mask, build_mask_from_boxes
from .stability import erase, search_and_replace

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_PROMPT = (
    "semi-transparent watermark overlay on top of the photo, "
    "brand logo, company name or website url stamp"
)
DEFAULT_REPLACE_PROMPT = (
    "seamless original background matching surrounding pixels"
)
DEFAULT_GROW_MASK = 5
DETECT_GROW_MASK = 8


class NoWatermarkDetected(RuntimeError):
    """Raised by detect-mode pipeline when OCR finds no watermark-like text."""


async def clean_image_dewatermark(image_bytes: bytes) -> bytes:
    """Default: Dewatermark.ai auto-erase — handles detection internally."""
    api_key = settings.DEWATERMARK_API_KEY
    if not api_key:
        raise RuntimeError("DEWATERMARK_API_KEY is not configured")
    url = getattr(settings, "DEWATERMARK_API_URL", None)
    kwargs = {"url": url} if url else {}
    return await dewatermark_erase(api_key, image_bytes, **kwargs)


async def clean_image_detect(image_bytes: bytes) -> tuple[bytes, list[TextBox]]:
    """OCR-detect watermark bboxes, build a tight mask, run Stability AI Erase."""
    api_key = _require_stability_key()
    boxes = await asyncio.to_thread(detect_watermark_boxes, image_bytes)
    if not boxes:
        raise NoWatermarkDetected("OCR did not find watermark-like text")

    rects = [(b.x, b.y, b.w, b.h) for b in boxes]
    logger.info("Detected watermark boxes: %s", rects)
    mask_bytes = build_mask_from_boxes(image_bytes, rects)
    cleaned = await erase(api_key, image_bytes, mask_bytes, grow_mask=DETECT_GROW_MASK)
    return cleaned, boxes


async def clean_image_auto(
    image_bytes: bytes,
    *,
    search_prompt: str = DEFAULT_SEARCH_PROMPT,
    prompt: str = DEFAULT_REPLACE_PROMPT,
    grow_mask: int = DEFAULT_GROW_MASK,
    passes: int = 1,
) -> bytes:
    """Generative fallback — Stability AI Search-and-Replace, no mask needed."""
    api_key = _require_stability_key()
    result = image_bytes
    for _ in range(max(1, passes)):
        result = await search_and_replace(
            api_key, result, search_prompt, prompt, grow_mask=grow_mask
        )
    return result


async def clean_image_with_mask(image_bytes: bytes, **mask_kwargs) -> bytes:
    """Manual-mask fallback — Stability AI Erase with a user-defined rectangle."""
    api_key = _require_stability_key()
    mask_bytes = build_default_mask(image_bytes, **mask_kwargs)
    return await erase(api_key, image_bytes, mask_bytes, grow_mask=DEFAULT_GROW_MASK)


def _require_stability_key() -> str:
    api_key = settings.STABILITY_API_KEY
    if not api_key:
        raise RuntimeError("STABILITY_API_KEY is not configured")
    return api_key
