import json
import logging

import httpx
from django.conf import settings

from apps.listings.models import Listing

logger = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Hard cap so a runaway generation can never break the PDF layout.
MAX_CHARS = 1000

# Max features we accept from Claude and max chars per feature label.
MAX_FEATURES = 8
MAX_FEATURE_CHARS = 60


async def generate_description(listing: Listing) -> str:
    """Ask Claude for a 5–6 line property description for the PDF.

    Returns an empty string on any failure — callers should fall back to the
    listing's existing description.
    """
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set; skipping AI description")
        return ""

    prompt = _build_prompt(listing)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": settings.ANTHROPIC_MODEL,
                    "max_tokens": 400,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
    except httpx.HTTPError:
        logger.exception("Claude request failed for listing=%s", listing.id)
        return ""

    if response.status_code != 200:
        logger.error(
            "Claude API %s for listing=%s: %s",
            response.status_code, listing.id, response.text[:500],
        )
        return ""

    try:
        payload = response.json()
    except ValueError:
        logger.exception("Claude returned non-JSON for listing=%s", listing.id)
        return ""

    blocks = payload.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()

    if not text or len(text) > MAX_CHARS:
        logger.warning(
            "Claude output rejected for listing=%s (len=%d): %r",
            listing.id, len(text), text[:200],
        )
        return ""

    logger.info("Claude description generated listing=%s chars=%d", listing.id, len(text))
    return text


async def generate_features(listing: Listing) -> list[str]:
    """Ask Claude to extract 5–7 short property features as a JSON array.

    Returns an empty list on any failure — caller decides what to do (typically
    leave ``listing.features`` empty and render an em-dash placeholder).
    """
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set; skipping AI features")
        return []

    prompt = _build_features_prompt(listing)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": settings.ANTHROPIC_MODEL,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
    except httpx.HTTPError:
        logger.exception("Claude features request failed for listing=%s", listing.id)
        return []

    if response.status_code != 200:
        logger.error(
            "Claude features API %s for listing=%s: %s",
            response.status_code, listing.id, response.text[:500],
        )
        return []

    try:
        payload = response.json()
    except ValueError:
        logger.exception("Claude features returned non-JSON for listing=%s", listing.id)
        return []

    blocks = payload.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()

    features = _parse_features(text)
    if not features:
        logger.warning(
            "Claude features rejected for listing=%s: %r",
            listing.id, text[:200],
        )
        return []

    logger.info(
        "Claude features generated listing=%s count=%d: %s",
        listing.id, len(features), features,
    )
    return features


def _parse_features(text: str) -> list[str]:
    """Pull a JSON list of strings out of Claude's response.

    Tolerates ```json``` code fences and trailing prose.
    """
    if not text:
        return []
    stripped = text.strip()

    # Drop a leading code fence (```json or ```).
    if stripped.startswith("```"):
        first_nl = stripped.find("\n")
        if first_nl != -1:
            stripped = stripped[first_nl + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        stripped = stripped.strip()

    # Most permissive: find the first [...] block.
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start == -1 or end <= start:
        return []
    candidate = stripped[start : end + 1]

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    out: list[str] = []
    for item in parsed:
        if not isinstance(item, str):
            continue
        cleaned = item.strip().strip("•-· ").strip()
        if cleaned and len(cleaned) <= MAX_FEATURE_CHARS:
            out.append(cleaned)
        if len(out) >= MAX_FEATURES:
            break
    return out


def _build_features_prompt(listing: Listing) -> str:
    desc = (listing.description or "").strip()[:3000]
    lines = [
        "Extract the key features of this property for a PDF presentation.",
        "",
        "Rules:",
        "- 5–7 features, each 1–4 words, Title Case.",
        "- Examples of good items: \"Balcony\", \"Sea View\", \"Covered Parking\", "
        "\"Shared Pool\", \"Built-in Wardrobes\", \"24/7 Security\", \"Maid's Room\".",
        "- Pick concrete amenities, views, and finishing — what makes the property "
        "stand out.",
        "- Do NOT include price, bedroom count, bathroom count, area, or "
        "location/address (those are shown elsewhere on the PDF).",
        "- If the description is sparse, infer plausible defaults for this kind of "
        "property (e.g. apartment in Dubai usually has Balcony, Covered Parking, "
        "Shared Pool, Shared Gym, Security).",
        "- Output STRICTLY a JSON array of strings. No preamble, no commentary, no "
        "code fences.",
        "",
        "Property:",
    ]
    if listing.title:
        lines.append(f"- Title: {listing.title}")
    if listing.property_type:
        lines.append(f"- Type: {listing.property_type}")
    if listing.address:
        lines.append(f"- Location: {listing.address}")
    if desc:
        lines.append(f"- Description: {desc}")
    lines.append("")
    lines.append("JSON array:")
    return "\n".join(lines)


def _build_prompt(listing: Listing) -> str:
    lines = [
        "Write a clean, professional real-estate property description in English "
        "for a PDF presentation.",
        "",
        "Rules:",
        "- 5–6 short lines, ~70 words maximum.",
        "- One flowing paragraph (or two short ones). No bullet points, no headers.",
        "- Factual and elegant. Avoid marketing fluff like \"stunning\", \"luxurious\", "
        "\"breathtaking\". No exclamation marks.",
        "- Mention the location, the layout, and at most 1–2 standout features.",
        "- Output the description text only — no preamble, no quotes, no commentary.",
        "",
        "Listing data:",
    ]
    if listing.title:
        lines.append(f"- Title: {listing.title}")
    if listing.property_type:
        lines.append(f"- Type: {listing.property_type}")
    if listing.address:
        lines.append(f"- Location: {listing.address}")
    if listing.rooms is not None:
        lines.append(f"- Bedrooms: {listing.rooms}")
    if listing.bathrooms is not None:
        lines.append(f"- Bathrooms: {listing.bathrooms}")
    if listing.area_sqft:
        lines.append(f"- Area: {int(round(listing.area_sqft))} sqft")
    elif listing.area_sqm:
        lines.append(f"- Area: {listing.area_sqm:g} m²")
    if listing.features:
        lines.append(f"- Features: {', '.join(listing.features)}")
    if listing.description:
        snippet = listing.description.strip()[:2000]
        lines.append(f"- Original long description: {snippet}")
    return "\n".join(lines)
