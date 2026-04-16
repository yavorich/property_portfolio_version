import asyncio

from asgiref.sync import async_to_sync


def ptb_async_to_sync(func):
    """
    Декоратор для асинхронной работы с python telegram bot
    """

    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(func(*args, **kwargs))
        except RuntimeError:
            return async_to_sync(func)(*args, **kwargs)

    return wrapper
