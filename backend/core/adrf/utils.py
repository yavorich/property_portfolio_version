from django.conf import settings


def non_atomic_request(view):
    view._non_atomic_requests = set(settings.DATABASES.keys())
    return view
