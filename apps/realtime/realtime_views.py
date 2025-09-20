from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.core.models import SlackWorkspace, SlackUser, SlackChannel
import json
import logging

logger = logging.getLogger('slack_api')


class RealtimeDataView(TemplateView):
    """
    Dedicated real-time data view for Slack messages
    """
    template_name = 'realtime/data.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get user's workspaces if authenticated
        if self.request.user.is_authenticated:
            user_workspaces = SlackWorkspace.objects.filter(
                slackuser__user=self.request.user,
                is_active=True
            ).distinct()
            context['workspaces'] = user_workspaces
        else:
            context['workspaces'] = []

        context['websocket_url'] = '/ws/slack/messages/'
        context['notifications_url'] = '/ws/slack/notifications/'

        return context


@csrf_exempt
@require_http_methods(["POST"])
def send_realtime_test_message(request):
    """
    API endpoint to send test messages for real-time testing
    """
    try:
        data = json.loads(request.body)
        message_type = data.get('type', 'channel_message')
        count = data.get('count', 1)

        channel_layer = get_channel_layer()
        if not channel_layer:
            return JsonResponse({
                'success': False,
                'error': 'Channel layer not configured'
            })

        # Send test messages based on type
        for i in range(count):
            if message_type == 'channel_message':
                test_message = {
                    'id': f'realtime_test_{i+1}',
                    'channel_id': 'C123456789',
                    'channel_name': 'general',
                    'channel_type': 'public_channel',
                    'user_id': 'U987654321',
                    'text': f'Real-time test message #{i+1}',
                    'timestamp': str(timezone.now().timestamp()),
                    'thread_ts': None,
                    'is_thread_reply': False,
                    'is_dm': False,
                    'workspace_id': 'test_workspace_1',
                    'workspace_name': 'Real-time Test Workspace',
                    'created_at': timezone.now().isoformat(),
                    'event_type': 'realtime_test_message'
                }

                # Broadcast to WebSocket groups
                async_to_sync(channel_layer.group_send)('slack_messages_anonymous', {
                    'type': 'slack_channel_message',
                    'message': test_message
                })

            elif message_type == 'dm':
                test_dm = {
                    'id': f'realtime_dm_{i+1}',
                    'channel_id': f'D789456{i:03d}',
                    'channel_name': None,
                    'channel_type': 'im',
                    'user_id': 'U555666777',
                    'text': f'Real-time test DM #{i+1}',
                    'timestamp': str(timezone.now().timestamp()),
                    'thread_ts': None,
                    'is_thread_reply': False,
                    'is_dm': True,
                    'workspace_id': 'test_workspace_1',
                    'workspace_name': 'Real-time Test Workspace',
                    'created_at': timezone.now().isoformat(),
                    'event_type': 'realtime_test_dm'
                }

                async_to_sync(channel_layer.group_send)('slack_messages_anonymous', {
                    'type': 'slack_dm',
                    'message': test_dm
                })

            elif message_type == 'notification':
                test_notification = {
                    'type': 'realtime_test',
                    'data': {
                        'message': f'Real-time test notification #{i+1}',
                        'timestamp': timezone.now().isoformat(),
                        'source': 'realtime_test',
                        'event_type': 'test_notification'
                    }
                }

                async_to_sync(channel_layer.group_send)('slack_notifications_anonymous', {
                    'type': 'slack_notification',
                    'notification': test_notification
                })

        return JsonResponse({
            'success': True,
            'message': f'Sent {count} real-time test {message_type} message(s)',
            'count': count,
            'type': message_type
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON payload'
        })
    except Exception as e:
        logger.error(f'Error sending real-time test message: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        })


def realtime_stats(request):
    """
    API endpoint to get real-time statistics
    """
    try:
        stats = {
            'total_workspaces': SlackWorkspace.objects.filter(is_active=True).count(),
            'total_channels': SlackChannel.objects.filter(is_archived=False).count(),
            'connected_users': 0,  # This would require tracking active WebSocket connections
            'realtime_enabled': True,
        }

        if request.user.is_authenticated:
            user_workspaces = SlackWorkspace.objects.filter(
                slackuser__user=request.user,
                is_active=True
            ).distinct()
            stats['user_workspaces'] = user_workspaces.count()

            user_channels = SlackChannel.objects.filter(
                workspace__in=user_workspaces,
                is_archived=False
            ).count()
            stats['user_channels'] = user_channels

        return JsonResponse({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        logger.error(f'Error getting real-time stats: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        })