import asyncio
import logging
import re
from urllib.parse import urlparse

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from apps.account.models import User

logger = logging.getLogger(__name__)

BAYUT_HOSTS = {"bayut.com", "www.bayut.com"}
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
            "Не вижу ссылки в сообщении. Пришлите ссылку на листинг Bayut."
        )
        return

    url = match.group(0)
    if not _is_bayut_url(url):
        await message.reply_text("Поддерживаются только ссылки на Bayut.com.")
        return

    status = await message.reply_text("✅ Принято в работу")
    try:
        await _run_mock_pipeline(url, status, user)
    except Exception:
        logger.exception("Pipeline failed for %s", url)
        await status.edit_text("❌ Ошибка при обработке. Попробуйте позже.")


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


def _is_bayut_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host in BAYUT_HOSTS


async def _run_mock_pipeline(url: str, status, user: User) -> None:
    """Mock pipeline with staged status updates. Real scraping / watermark /
    presentation modules will replace each sleep block later."""

    await status.edit_text("📥 Скачиваю фото и данные объекта…")
    await asyncio.sleep(1.5)

    await status.edit_text("🧹 Удаляю водяные знаки…")
    await asyncio.sleep(1.5)

    await status.edit_text("🧾 Формирую презентацию…")
    await asyncio.sleep(1.5)

    await status.edit_text(
        "✅ Готово!\n\n"
        f"Объект: <i>{url}</i>\n"
        "Презентация будет прикреплена, когда пайплайн парсинга/обработки "
        "будет подключён (сейчас — мок)."
    )


start_handlers = [
    CommandHandler("start", start),
    CommandHandler("help", help_command),
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
]
