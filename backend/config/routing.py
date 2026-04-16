from django.urls import path
from channels.routing import URLRouter


websocket_urlpatterns = [
    path("ws/", URLRouter([])),
]
