from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/slack/messages/$', consumers.SlackMessageConsumer.as_asgi()),
    re_path(r'ws/slack/notifications/$', consumers.SlackNotificationConsumer.as_asgi()),
]