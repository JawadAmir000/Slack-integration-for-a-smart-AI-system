from django.urls import path, include
from . import views

app_name = 'realtime'

urlpatterns = [
    # Slack Events API webhooks (multi-tenant) - handle both with and without trailing slash
    path('events', views.SlackEventsWebhookView.as_view(), name='slack_events_webhook_no_slash'),
    path('events/', views.SlackEventsWebhookView.as_view(), name='slack_events_webhook'),
    path('events/<str:client_identifier>/', views.SlackEventsWebhookView.as_view(), name='slack_events_webhook_client'),

    # Slack Interactive Components webhooks (multi-tenant)
    path('interactive/', views.SlackInteractiveWebhookView.as_view(), name='slack_interactive_webhook'),
    path('interactive/<str:client_identifier>/', views.SlackInteractiveWebhookView.as_view(), name='slack_interactive_webhook_client'),

    # Legacy endpoint for backward compatibility
    path('webhook/', views.slack_events_webhook, name='slack_webhook_legacy'),

    # Test page for WebSocket connections
    path('test/', views.websocket_test_view, name='websocket_test'),
]