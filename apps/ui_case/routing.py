# apps/ui_case/routing.py
from django.urls import re_path
from .consumers import RunConsumer

websocket_urlpatterns = [
    re_path(r"^api/ws/run/(?P<run_id>[0-9a-f-]+)/$", RunConsumer.as_asgi()),
]
