from django.urls import path
from . import dashboard_views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard main page
    path('', dashboard_views.DashboardView.as_view(), name='index'),

    # API endpoints for dashboard
    path('api/test-message/', dashboard_views.send_test_message, name='send_test_message'),
    path('api/stats/', dashboard_views.dashboard_stats, name='dashboard_stats'),
    path('api/workspace/<uuid:workspace_id>/channels/', dashboard_views.workspace_channels, name='workspace_channels'),
]