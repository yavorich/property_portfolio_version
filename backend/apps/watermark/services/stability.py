import logging

import httpx

logger = logging.getLogger(__name__)

ERASE_URL = "https://api.stability.ai/v2beta/stable-image/edit/erase"
SEARCH_AND_REPLACE_URL = (
    "https://api.stability.ai/v2beta/stable-image/edit/search-and-replace"
)
REQUEST_TIMEOUT = httpx.Timeout(120.0, connect=15.0)


class StabilityAPIError(RuntimeError):
    pass


async def erase(
    api_key: str,
    image_bytes: bytes,
    mask_bytes: bytes,
    output_format: str = "png",
    grow_mask: int = 5,
) -> bytes:
    """Stability AI Erase — requires an explicit mask (white = erase)."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            ERASE_URL,
            headers=_headers(api_key),
            files={
                "image": ("image.png", image_bytes, "image/png"),
                "mask": ("mask.png", mask_bytes, "image/png"),
            },
            data={"output_format": output_format, "grow_mask": str(grow_mask)},
        )
    return _unwrap(response, "erase")


async def search_and_replace(
    api_key: str,
    image_bytes: bytes,
    search_prompt: str,
    prompt: str,
    output_format: str = "png",
    grow_mask: int = 5,
) -> bytes:
    """Stability AI Search and Replace — finds content by text description and
    replaces it. No mask required. Ideal for watermarks whose position isn't known.
    """
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            SEARCH_AND_REPLACE_URL,
            headers=_headers(api_key),
            files={"image": ("image.png", image_bytes, "image/png")},
            data={
                "prompt": prompt,
                "search_prompt": search_prompt,
                "output_format": output_format,
                "grow_mask": str(grow_mask),
            },
        )
    return _unwrap(response, "search-and-replace")


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "image/*",
    }


def _unwrap(response: httpx.Response, label: str) -> bytes:
    if response.status_code != 200:
        detail = response.text[:500]
        logger.error("Stability %s failed: %s %s", label, response.status_code, detail)
        raise StabilityAPIError(
            f"Stability API ({label}) returned {response.status_code}: {detail}"
        )
    return response.content
