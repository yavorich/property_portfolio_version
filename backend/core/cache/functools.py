from django.core.cache import cache


def get_or_cache(key, timeout):
    def decorator(func):
        def wrapper(*args, **kwargs):
            response = cache.get(key)
            if response is None:
                response = func(*args, **kwargs)
                if hasattr(response, "render") and callable(response.render):
                    response.add_post_render_callback(
                        lambda r: cache.set(key, r, timeout)
                    )
                else:
                    cache.set(key, response, timeout)

            return response

        return wrapper

    return decorator


def delete_cache(key):
    cache.delete(key)
