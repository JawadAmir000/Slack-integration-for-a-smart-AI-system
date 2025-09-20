from django.urls import path
from . import realtime_views

app_name = 'realtime'

urlpatterns = [
    # Real-time data page
    path('', realtime_views.RealtimeDataView.as_view(), name='data'),

    # API endpoints for real-time data
    path('test-message/', realtime_views.send_realtime_test_message, name='send_test_message'),
    path('stats/', realtime_views.realtime_stats, name='stats'),
]