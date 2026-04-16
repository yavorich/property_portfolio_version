import telegram_bot.django_setup  # noqa: F401  (initialises Django before settings import)

import asyncio
import logging

from django.conf import settings
from telegram import Bot, BotCommand, Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import Application, ApplicationBuilder, ContextTypes
from telegram.request import HTTPXRequest

from telegram_bot.handlers import start_handlers
from telegram_bot.proxies import load_proxies

logger = logging.getLogger(__name__)

HEALTHCHECK_CONNECT_TIMEOUT = 5.0
HEALTHCHECK_READ_TIMEOUT = 10.0


async def _check_proxy(proxy: str | None) -> bool:
    request = (
        HTTPXRequest(
            proxy=proxy,
            connect_timeout=HEALTHCHECK_CONNECT_TIMEOUT,
            read_timeout=HEALTHCHECK_READ_TIMEOUT,
        )
        if proxy
        else None
    )
    bot = Bot(settings.TELEGRAM_BOT_TOKEN, request=request)
    try:
        await bot.initialize()
        await bot.get_me()
        return True
    except Exception as exc:
        logger.warning("Proxy %s healthcheck failed: %s", proxy or "direct", exc)
        return False
    finally:
        try:
            await bot.shutdown()
        except Exception:
            pass


def _pick_working_proxy() -> str | None:
    proxies = load_proxies()
    for idx, proxy in enumerate(proxies, start=1):
        label = proxy or "direct connection"
        logger.info("Healthcheck %d/%d via %s", idx, len(proxies), label)
        if asyncio.run(_check_proxy(proxy)):
            logger.info("Proxy OK: %s", label)
            return proxy
    raise RuntimeError(f"No working proxy among {len(proxies)} option(s)")


BOT_COMMANDS = [
    BotCommand("start", "Начать работу"),
    BotCommand("help", "Как пользоваться ботом"),
]


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(BOT_COMMANDS)


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Swallow transient network errors so the handler chain keeps running.

    PTB propagates exceptions out of handlers when no error handler is registered,
    so a flaky SOCKS5 proxy reply would otherwise surface to the user as a crash.
    """
    err = context.error
    if isinstance(err, (NetworkError, TimedOut)):
        logger.warning("Transient network error: %r", err)
        return
    logger.exception("Unhandled handler error", exc_info=err)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте ещё раз."
            )
    except Exception:
        pass


def run_polling() -> None:
    """Run bot in polling mode. Picks the first working proxy, then starts the app once."""

    proxy = _pick_working_proxy()

    # asyncio.run() above left event loop policy with no current loop; give PTB a fresh one.
    asyncio.set_event_loop(asyncio.new_event_loop())

    builder = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).post_init(_post_init)
    if proxy:
        builder = builder.request(HTTPXRequest(proxy=proxy))
        builder = builder.get_updates_request(HTTPXRequest(proxy=proxy))
    application = builder.build()

    for handlers in [start_handlers]:
        application.add_handlers(handlers)

    application.add_error_handler(_on_error)

    logger.info("Starting polling via %s", proxy or "direct connection")
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_polling()
