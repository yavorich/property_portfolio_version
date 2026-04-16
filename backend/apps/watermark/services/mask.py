from io import BytesIO

from PIL import Image, ImageDraw

# Default rectangle geometry as fractions of image width / height.
# Bottom-center band — typical Bayut watermark placement.
DEFAULT_MASK = {
    "x_ratio": 0.20,
    "y_ratio": 0.83,
    "w_ratio": 0.60,
    "h_ratio": 0.14,
}


def build_default_mask(
    image_bytes: bytes,
    *,
    x_ratio: float = DEFAULT_MASK["x_ratio"],
    y_ratio: float = DEFAULT_MASK["y_ratio"],
    w_ratio: float = DEFAULT_MASK["w_ratio"],
    h_ratio: float = DEFAULT_MASK["h_ratio"],
) -> bytes:
    """Return a PNG mask covering the area to erase.

    Mask convention (Stability AI erase):
      - white (255) = erase
      - black (0)   = keep
    """
    with Image.open(BytesIO(image_bytes)) as img:
        width, height = img.size

    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    x, y, rect_w, rect_h = _resolve_rect(width, height, x_ratio, y_ratio, w_ratio, h_ratio)
    draw.rectangle((x, y, x + rect_w, y + rect_h), fill=255)

    buffer = BytesIO()
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


def build_overlay_preview(
    image_bytes: bytes,
    *,
    x_ratio: float = DEFAULT_MASK["x_ratio"],
    y_ratio: float = DEFAULT_MASK["y_ratio"],
    w_ratio: float = DEFAULT_MASK["w_ratio"],
    h_ratio: float = DEFAULT_MASK["h_ratio"],
) -> bytes:
    """Return the original image with a semi-transparent red rectangle drawn
    over the mask area — for tuning mask geometry visually."""

    with Image.open(BytesIO(image_bytes)) as src:
        base = src.convert("RGBA")
    width, height = base.size

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x, y, rect_w, rect_h = _resolve_rect(width, height, x_ratio, y_ratio, w_ratio, h_ratio)
    draw.rectangle(
        (x, y, x + rect_w, y + rect_h),
        fill=(255, 0, 0, 96),
        outline=(255, 0, 0, 255),
        width=max(3, min(width, height) // 200),
    )

    combined = Image.alpha_composite(base, overlay).convert("RGB")
    buffer = BytesIO()
    combined.save(buffer, format="PNG")
    return buffer.getvalue()


def build_mask_from_boxes(
    image_bytes: bytes,
    boxes: list[tuple[int, int, int, int]],
    *,
    padding: int = 6,
) -> bytes:
    """Return a PNG mask with white rectangles at the given (x, y, w, h) boxes."""
    with Image.open(BytesIO(image_bytes)) as img:
        width, height = img.size

    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for x, y, w, h in boxes:
        x0 = max(0, x - padding)
        y0 = max(0, y - padding)
        x1 = min(width, x + w + padding)
        y1 = min(height, y + h + padding)
        draw.rectangle((x0, y0, x1, y1), fill=255)

    buffer = BytesIO()
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


def build_boxes_overlay(
    image_bytes: bytes,
    boxes: list[tuple[int, int, int, int]],
    *,
    padding: int = 6,
) -> bytes:
    """Return the original image with semi-transparent red rectangles over each bbox."""
    with Image.open(BytesIO(image_bytes)) as src:
        base = src.convert("RGBA")
    width, height = base.size

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    outline_width = max(3, min(width, height) // 250)
    for x, y, w, h in boxes:
        x0 = max(0, x - padding)
        y0 = max(0, y - padding)
        x1 = min(width, x + w + padding)
        y1 = min(height, y + h + padding)
        draw.rectangle(
            (x0, y0, x1, y1),
            fill=(255, 0, 0, 96),
            outline=(255, 0, 0, 255),
            width=outline_width,
        )

    combined = Image.alpha_composite(base, overlay).convert("RGB")
    buffer = BytesIO()
    combined.save(buffer, format="PNG")
    return buffer.getvalue()


def _resolve_rect(
    width: int, height: int, x_ratio: float, y_ratio: float, w_ratio: float, h_ratio: float
) -> tuple[int, int, int, int]:
    x = max(0, int(width * x_ratio))
    y = max(0, int(height * y_ratio))
    rect_w = min(width - x, int(width * w_ratio))
    rect_h = min(height - y, int(height * h_ratio))
    return x, y, rect_w, rect_h
