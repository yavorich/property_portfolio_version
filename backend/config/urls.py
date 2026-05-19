from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, include, re_path
from django.views.static import serve


urlpatterns = [
    # path(
    #     "api/v1/",
    #     include(
    #         [
    #             path("", include("apps.account.endpoints")),
    #         ]
    #     ),
    # ),
    path("admin/", admin.site.urls),
]

# Обслуживаем /media/ и /static/ напрямую через Django вне зависимости от DEBUG —
# нужно для админского iframe-превью PDF на :8000 (мимо nginx). Для прод-трафика
# через nginx эти роуты не активируются: nginx режет /media/ и /static/ сам.
urlpatterns += staticfiles_urlpatterns()  # type: ignore
urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        {"document_root": settings.MEDIA_ROOT},
    ),
    re_path(
        r"^static/(?P<path>.*)$",
        serve,
        {"document_root": settings.STATIC_ROOT},
    ),
]
