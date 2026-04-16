import base64
import logging

import httpx

logger = logging.getLogger(__name__)

DEFAULT_URL = "https://platform.dewatermark.ai/api/object_removal/v2/erase_watermark"
REQUEST_TIMEOUT = httpx.Timeout(120.0, connect=15.0)


class DewatermarkAPIError(RuntimeError):
    pass


async def erase_watermark(
    api_key: str,
    image_bytes: bytes,
    *,
    remove_text: bool = True,
    remove_logo: bool = True,
    url: str = DEFAULT_URL,
) -> bytes:
    """Call Dewatermark.ai Erase Watermark and return cleaned image bytes.

    Auto-detects and removes watermarks — no mask needed.
    """
    headers = {"X-API-KEY": api_key}
    data = {
        "remove_text": "true" if remove_text else "false",
        "remove_logo": "true" if remove_logo else "false",
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            url,
            headers=headers,
            files={
                "original_preview_image": ("image.png", image_bytes, "image/png"),
            },
            data=data,
        )

    if response.status_code != 200:
        detail = response.text[:1000]
        logger.error(
            "Dewatermark erase failed url=%s status=%s header_keys=%s "
            "data=%s resp=%s",
            url,
            response.status_code,
            list(headers.keys()),
            data,
            detail,
        )
        raise DewatermarkAPIError(
            f"Dewatermark API returned {response.status_code}: {detail}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise DewatermarkAPIError(f"Dewatermark returned non-JSON response: {exc}") from exc

    edited = payload.get("edited_image") or {}
    image_b64 = edited.get("image") if isinstance(edited, dict) else None
    if not image_b64:
        raise DewatermarkAPIError(
            f"Dewatermark response missing edited_image.image: {payload!r}"
        )
    try:
        return base64.b64decode(image_b64)
    except (ValueError, TypeError) as exc:
        raise DewatermarkAPIError(f"Cannot decode Dewatermark base64: {exc}") from exc
