from asgiref.sync import async_to_sync


def celery_async(func):
    def wrapper(*args, **kwargs):
        return async_to_sync(func)(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper
