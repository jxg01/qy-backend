"""
ASGI config for qy_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

from channels.routing import ProtocolTypeRouter, URLRouter
from apps.ui_case.routing import websocket_urlpatterns as ui_case_ws

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qy_backend.settings')

# application = get_asgi_application()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter([
        *ui_case_ws,         # ★ 把 ui_case 的 WS 路由挂进来
    ]),
})


