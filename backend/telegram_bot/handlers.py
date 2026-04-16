import asyncio
import logging
import re
from io import BytesIO
from urllib.parse import urlparse

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from apps.account.models import User
from apps.listings.models import Listing
from apps.listings.parsers import ParserNotFound
from apps.listings.services import process_url
from apps.watermark.services import (
    DEFAULT_MASK,
    DEFAULT_SEARCH_PROMPT,
    NoWatermarkDetected,
    build_boxes_overlay,
    build_overlay_preview,
    clean_image_auto,
    clean_image_detect,
    clean_image_dewatermark,
    clean_image_with_mask,
    detect_watermark_boxes,
)

logger = logging.getLogger(__name__)

SUPPORTED_HOSTS = {
    "bayut.com",
    "www.bayut.com",
    "propertyfinder.ae",
    "www.propertyfinder.ae",
}
URL_RE = re.compile(r"https?://\S+")
COORDS_RE = re.compile(
    r"([01]?\.?\d+)\s+([01]?\.?\d+)\s+([01]?\.?\d+)\s+([01]?\.?\d+)"
)
DEBUG_RE = re.compile(r"\bdebug\b", re.IGNORECASE)
MASK_KEYWORD_RE = re.compile(r"\bmask\b", re.IGNORECASE)
AUTO_KEYWORD_RE = re.compile(r"\bauto\b", re.IGNORECASE)
DETECT_KEYWORD_RE = re.compile(r"\bdetect\b", re.IGNORECASE)
DEWATERMARK_KEYWORD_RE = re.compile(r"\bdewatermark\b", re.IGNORECASE)
STABILITY_KEYWORD_RE = re.compile(r"\bstability\b", re.IGNORECASE)
PASSES_RE = re.compile(r"\bx([2-5])\b", re.IGNORECASE)

WELCOME_TEXT = (
    "<b>Добро пожаловать!</b>\n\n"
    "Пришлите <b>фотографию</b> — бот автоматически удалит водяной знак "
    "и вернёт очищенное изображение.\n\n"
    "Также можно прислать ссылку на листинг Bayut — бот соберёт данные "
    "об объекте и скачает фото (парсинг в разработке).\n\n"
    "Команды:\n"
    "• /start — это сообщение\n"
    "• /help — как пользоваться"
)

HELP_TEXT = (
    "<b>Удаление водяных знаков</b>\n"
    "Просто пришлите фотографию — бот вернёт очищенное изображение.\n\n"
    "<b>Парсинг листингов</b>\n"
    "Пришлите ссылку вида <code>https://www.bayut.com/property/details-…</code>."
)

BLOCKED_TEXT = "Ваш аккаунт заблокирован."


async def start(update: Update, context: CallbackContext) -> None:
    user = await _authorize(update)
    if user is None:
        return
    if not user.is_active:
        await update.effective_message.reply_text(BLOCKED_TEXT)
        return
    await update.effective_message.reply_text(WELCOME_TEXT, parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: CallbackContext) -> None:
    user = await _authorize(update)
    if user is None or not user.is_active:
        return
    await update.effective_message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def handle_photo(update: Update, context: CallbackContext) -> None:
    user = await _authorize(update)
    if user is None:
        return
    if not user.is_active:
        await update.effective_message.reply_text(BLOCKED_TEXT)
        return

    message = update.effective_message
    file_id = _pick_image_file_id(message)
    if not file_id:
        return

    mode = _parse_caption(message.caption)

    status = await message.reply_text("📥 Скачиваю изображение…")
    try:
        tg_file = await context.bot.get_file(file_id)
        image_bytes = bytes(await tg_file.download_as_bytearray())

        kind = mode["kind"]

        if kind == "debug_mask":
            await status.edit_text("🔍 Готовлю превью ручной маски…")
            preview = build_overlay_preview(image_bytes, **mode["mask_kwargs"])
            await message.reply_document(
                document=BytesIO(preview),
                filename="mask_preview.png",
                caption=f"Маска: {_format_geometry(mode['mask_kwargs'])}",
            )
            await status.delete()
            return

        if kind == "debug_detect":
            await status.edit_text("🔍 Ищу текст через OCR…")
            boxes = await asyncio.to_thread(detect_watermark_boxes, image_bytes)
            if not boxes:
                await status.edit_text(
                    "⚠️ OCR не нашёл текстовых зон. Попробуйте <code>auto</code> или "
                    "ручную маску (<code>x y w h</code>).",
                    parse_mode=ParseMode.HTML,
                )
                return
            rects = [(b.x, b.y, b.w, b.h) for b in boxes]
            preview = build_boxes_overlay(image_bytes, rects)
            detected = "; ".join(f"«{b.text}» ({b.conf}%)" for b in boxes)
            await message.reply_document(
                document=BytesIO(preview),
                filename="detection_preview.png",
                caption=f"Найдено: {detected}",
            )
            await status.delete()
            return

        if kind == "dewatermark":
            await status.edit_text("🧹 Удаляю водяной знак через Dewatermark.ai…")
            cleaned = await clean_image_dewatermark(image_bytes)
            caption = "Готово ✅\nРежим: Dewatermark.ai (auto)"

        elif kind == "mask":
            await status.edit_text(
                "🧹 Удаляю водяной знак (Stability Erase + ручная маска)…\n"
                f"Маска: {_format_geometry(mode['mask_kwargs'])}"
            )
            cleaned = await clean_image_with_mask(image_bytes, **mode["mask_kwargs"])
            caption = f"Готово ✅\nРежим: ручная маска\nМаска: {_format_geometry(mode['mask_kwargs'])}"

        elif kind == "auto":
            search_prompt = mode["search_prompt"] or DEFAULT_SEARCH_PROMPT
            passes = mode["passes"]
            await status.edit_text(
                "🧹 Удаляю водяной знак через Stability AI (auto)…\n"
                f"Ищу: <i>{search_prompt}</i>"
                + (f"\nПроходов: {passes}" if passes > 1 else ""),
                parse_mode=ParseMode.HTML,
            )
            cleaned = await clean_image_auto(
                image_bytes, search_prompt=search_prompt, passes=passes
            )
            caption = (
                f"Готово ✅\nРежим: auto (S&R)\nИскал: {search_prompt}"
                + (f"\nПроходов: {passes}" if passes > 1 else "")
            )

        else:  # "detect"
            await status.edit_text("🔍 Ищу водяной знак через OCR…")
            try:
                cleaned, boxes = await clean_image_detect(image_bytes)
            except NoWatermarkDetected:
                await status.edit_text(
                    "⚠️ OCR не нашёл текст. Пробую S&amp;R как резерв…",
                    parse_mode=ParseMode.HTML,
                )
                cleaned = await clean_image_auto(image_bytes)
                caption = "Готово ✅\nРежим: fallback auto (OCR не сработал)"
            else:
                detected = "; ".join(f"«{b.text}»" for b in boxes)
                caption = f"Готово ✅\nРежим: detect + erase\nНайдено: {detected}"

        await status.edit_text("📤 Отправляю результат…")
        await message.reply_document(
            document=BytesIO(cleaned),
            filename="cleaned.png",
            caption=caption,
        )
        await status.delete()
    except Exception:
        logger.exception("Watermark removal failed")
        await status.edit_text("❌ Ошибка при обработке изображения.")


async def handle_message(update: Update, context: CallbackContext) -> None:
    user = await _authorize(update)
    if user is None:
        return
    if not user.is_active:
        await update.effective_message.reply_text(BLOCKED_TEXT)
        return

    message = update.effective_message
    if not message or not message.text:
        return

    match = URL_RE.search(message.text)
    if not match:
        await message.reply_text(
            "Пришлите <b>фото</b> для удаления водяного знака, либо ссылку на "
            "листинг Bayut/Property Finder.",
            parse_mode=ParseMode.HTML,
        )
        return

    url = match.group(0)
    if not _is_supported(url):
        await message.reply_text("Поддерживаются только ссылки на Bayut и Property Finder.")
        return

    status = await message.reply_text("✅ Принято в работу")

    async def on_status(text: str) -> None:
        try:
            await status.edit_text(text, parse_mode=ParseMode.HTML)
        except BadRequest as exc:
            logger.debug("Status edit skipped: %s", exc)

    try:
        listing = await process_url(url, user, on_status)
    except ParserNotFound:
        await status.edit_text("Поддерживаются только ссылки на Bayut и Property Finder.")
        return
    except NotImplementedError as exc:
        await status.edit_text(str(exc) or "Парсер для этого источника ещё не готов.")
        return
    except Exception:
        logger.exception("Pipeline failed for %s", url)
        await status.edit_text("❌ Ошибка при обработке. Попробуйте позже.")
        return

    await on_status(_format_result(listing, await listing.photos.acount()))


async def _authorize(update: Update) -> User | None:
    """Register user on first contact, return the record for subsequent checks."""

    tg_user = update.effective_user
    if tg_user is None:
        return None

    telegram_name = tg_user.username.lower() if tg_user.username else None
    user, created = await User.objects.aget_or_create(
        telegram_id=tg_user.id,
        defaults={
            "telegram_name": telegram_name,
            "first_name": tg_user.first_name or "",
            "last_name": tg_user.last_name or "",
        },
    )
    if created:
        logger.info("Registered new user tg_id=%s name=%s", tg_user.id, telegram_name)
    return user


def _parse_caption(caption: str | None) -> dict:
    """Classify photo caption into a processing mode.

    Kinds:
      - ``"dewatermark"``  — Dewatermark.ai auto-erase (default, empty caption)
      - ``"detect"``       — OCR detection + Stability AI Erase
      - ``"auto"``         — Stability AI Search-and-Replace
      - ``"mask"``         — manual rectangular mask + Stability AI Erase
      - ``"debug_mask"``   — preview of manual mask, no API call
      - ``"debug_detect"`` — preview of OCR-detected regions, no API call
    """
    text = (caption or "").strip()
    debug = bool(DEBUG_RE.search(text))
    has_mask_keyword = bool(MASK_KEYWORD_RE.search(text))
    has_auto_keyword = bool(AUTO_KEYWORD_RE.search(text))
    has_detect_keyword = bool(DETECT_KEYWORD_RE.search(text))
    has_dewatermark_keyword = bool(DEWATERMARK_KEYWORD_RE.search(text))
    has_stability_keyword = bool(STABILITY_KEYWORD_RE.search(text))

    mask_kwargs: dict = {}
    coord_match = COORDS_RE.search(text)
    if coord_match:
        x, y, w, h = (float(v) for v in coord_match.groups())
        mask_kwargs = {
            "x_ratio": x,
            "y_ratio": y,
            "w_ratio": w,
            "h_ratio": h,
        }

    passes = 1
    if pmatch := PASSES_RE.search(text):
        passes = int(pmatch.group(1))

    # Strip control tokens so the remainder can serve as a free-form search_prompt.
    cleaned_prompt = DEBUG_RE.sub("", text)
    cleaned_prompt = MASK_KEYWORD_RE.sub("", cleaned_prompt)
    cleaned_prompt = AUTO_KEYWORD_RE.sub("", cleaned_prompt)
    cleaned_prompt = DETECT_KEYWORD_RE.sub("", cleaned_prompt)
    cleaned_prompt = DEWATERMARK_KEYWORD_RE.sub("", cleaned_prompt)
    cleaned_prompt = STABILITY_KEYWORD_RE.sub("", cleaned_prompt)
    cleaned_prompt = PASSES_RE.sub("", cleaned_prompt)
    if coord_match:
        cleaned_prompt = cleaned_prompt.replace(coord_match.group(0), "")
    cleaned_prompt = cleaned_prompt.strip()

    if debug:
        if has_mask_keyword or mask_kwargs:
            return {"kind": "debug_mask", "mask_kwargs": mask_kwargs, "search_prompt": "", "passes": 1}
        return {"kind": "debug_detect", "mask_kwargs": {}, "search_prompt": "", "passes": 1}

    if has_mask_keyword or mask_kwargs:
        return {"kind": "mask", "mask_kwargs": mask_kwargs, "search_prompt": "", "passes": 1}

    if has_detect_keyword:
        return {"kind": "detect", "mask_kwargs": {}, "search_prompt": "", "passes": 1}

    if has_auto_keyword or has_stability_keyword or (cleaned_prompt and not has_dewatermark_keyword):
        return {
            "kind": "auto",
            "mask_kwargs": {},
            "search_prompt": cleaned_prompt,
            "passes": passes,
        }

    # Default (empty caption or explicit `dewatermark`) → Dewatermark.ai
    return {"kind": "dewatermark", "mask_kwargs": {}, "search_prompt": "", "passes": 1}


def _format_geometry(mask_kwargs: dict) -> str:
    data = {**DEFAULT_MASK, **mask_kwargs}
    return (
        f"x={data['x_ratio']:g} y={data['y_ratio']:g} "
        f"w={data['w_ratio']:g} h={data['h_ratio']:g}"
    )


def _pick_image_file_id(message) -> str | None:
    if message.photo:
        # message.photo is a list of sizes; take the largest.
        return message.photo[-1].file_id
    if (
        message.document
        and message.document.mime_type
        and message.document.mime_type.startswith("image/")
    ):
        return message.document.file_id
    return None


def _is_supported(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host in SUPPORTED_HOSTS


def _format_result(listing: Listing, photo_count: int) -> str:
    lines = ["✅ <b>Готово!</b>", ""]
    if listing.title:
        lines.append(f"<b>{listing.title}</b>")
    if listing.address:
        lines.append(listing.address)
    if listing.price:
        lines.append(f"💰 {listing.price:,} {listing.currency}".replace(",", " "))
    specs = []
    if listing.rooms is not None:
        specs.append(f"{listing.rooms} комн.")
    if listing.bathrooms is not None:
        specs.append(f"{listing.bathrooms} с/у")
    if listing.area_sqm:
        specs.append(f"{listing.area_sqm:g} m²")
    if listing.floor:
        specs.append(f"этаж {listing.floor}")
    if specs:
        lines.append(" · ".join(specs))
    if listing.broker_name or listing.broker_phone:
        broker = listing.broker_name or "брокер"
        if listing.broker_phone:
            broker += f" · {listing.broker_phone}"
        lines.append(f"👤 {broker}")
    lines.append("")
    lines.append(f"🖼 Фото скачано: {photo_count}")
    return "\n".join(lines)


start_handlers = [
    CommandHandler("start", start),
    CommandHandler("help", help_command),
    MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo),
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
]
