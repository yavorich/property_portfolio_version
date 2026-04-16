from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, include


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

urlpatterns += staticfiles_urlpatterns()  # type: ignore
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
