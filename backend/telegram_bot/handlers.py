import logging
import re
from urllib.parse import urlparse

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from apps.account.models import User
from apps.listings.models import Listing
from apps.listings.parsers import ParserNotFound
from apps.listings.services import process_url

logger = logging.getLogger(__name__)

SUPPORTED_HOSTS = {
    "bayut.com",
    "www.bayut.com",
    "propertyfinder.ae",
    "www.propertyfinder.ae",
}
URL_RE = re.compile(r"https?://\S+")

WELCOME_TEXT = (
    "<b>Добро пожаловать!</b>\n\n"
    "Отправьте ссылку на листинг <b>Bayut.com</b>, и я:\n"
    "1. Соберу данные об объекте\n"
    "2. Удалю водяные знаки с фото\n"
    "3. Подготовлю презентацию объекта\n\n"
    "Команды:\n"
    "• /start — это сообщение\n"
    "• /help — как пользоваться"
)

HELP_TEXT = (
    "Пришлите сообщением ссылку вида:\n"
    "<code>https://www.bayut.com/property/details-…</code>\n\n"
    "Бот обработает её и вернёт готовую презентацию."
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
            "Не вижу ссылки в сообщении. Пришлите ссылку на листинг Bayut или Property Finder."
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
            # Telegram refuses "message is not modified" etc. — safe to ignore.
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
    lines.append("")
    lines.append("<i>Удаление водяных знаков и формирование презентации — следующий этап.</i>")
    return "\n".join(lines)


start_handlers = [
    CommandHandler("start", start),
    CommandHandler("help", help_command),
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
]
