import logging
from dataclasses import dataclass
from io import BytesIO

import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 40          # tesseract confidence 0..100
MERGE_PAD = 10               # px gap that still counts as "adjacent" when merging
BOX_PADDING = 6              # extra margin around each detected bbox in the mask

# Watermark-plausible zones (center of the bbox must fall inside at least one).
# Fractions of image size.
BOTTOM_THRESHOLD = 0.65
TOP_THRESHOLD = 0.10
SIDE_THRESHOLD = 0.15


@dataclass(frozen=True)
class TextBox:
    x: int
    y: int
    w: int
    h: int
    text: str
    conf: int


def detect_watermark_boxes(image_bytes: bytes) -> list[TextBox]:
    """Run OCR and return text boxes in watermark-plausible zones (bottom or corners)."""

    with Image.open(BytesIO(image_bytes)) as img:
        width, height = img.size
        rgb = img.convert("RGB")
        data = pytesseract.image_to_data(rgb, output_type=pytesseract.Output.DICT)

    boxes: list[TextBox] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = int(float(data["conf"][i]))
        except (ValueError, TypeError):
            continue
        if conf < MIN_CONFIDENCE:
            continue

        x, y = int(data["left"][i]), int(data["top"][i])
        w, h = int(data["width"][i]), int(data["height"][i])
        if w <= 0 or h <= 0:
            continue

        cx, cy = x + w / 2, y + h / 2
        in_zone = (
            cy > height * BOTTOM_THRESHOLD
            or cy < height * TOP_THRESHOLD
            or cx < width * SIDE_THRESHOLD
            or cx > width * (1 - SIDE_THRESHOLD)
        )
        if not in_zone:
            continue

        boxes.append(TextBox(x=x, y=y, w=w, h=h, text=text, conf=conf))

    merged = _merge(boxes)
    logger.info(
        "OCR detected %d watermark-like region(s) (from %d raw boxes)",
        len(merged), len(boxes),
    )
    return merged


def _merge(boxes: list[TextBox]) -> list[TextBox]:
    """Greedy union: merge boxes whose padded rects overlap or touch."""
    if not boxes:
        return []
    rects = [[b.x, b.y, b.w, b.h, b.text, b.conf] for b in boxes]
    changed = True
    while changed:
        changed = False
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                if _overlap(rects[i], rects[j], MERGE_PAD):
                    rects[i] = _union(rects[i], rects[j])
                    rects.pop(j)
                    changed = True
                    break
            if changed:
                break
    return [
        TextBox(x=r[0], y=r[1], w=r[2], h=r[3], text=r[4], conf=r[5])
        for r in rects
    ]


def _overlap(a, b, pad):
    ax, ay, aw, ah = a[:4]
    bx, by, bw, bh = b[:4]
    return not (
        ax + aw + pad < bx
        or bx + bw + pad < ax
        or ay + ah + pad < by
        or by + bh + pad < ay
    )


def _union(a, b):
    ax, ay, aw, ah = a[:4]
    bx, by, bw, bh = b[:4]
    x0, y0 = min(ax, bx), min(ay, by)
    x1, y1 = max(ax + aw, bx + bw), max(ay + ah, by + bh)
    text = f"{a[4]} {b[4]}".strip()
    conf = max(a[5], b[5])
    return [x0, y0, x1 - x0, y1 - y0, text, conf]
