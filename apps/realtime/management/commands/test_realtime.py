from django.core.management.base import BaseCommand
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.core.models import SlackWorkspace, SlackChannel, SlackMessage, SlackUser
import json


class Command(BaseCommand):
    help = 'Test real-time messaging system by sending simulated Slack events'

    def add_arguments(self, parser):
        parser.add_argument(
            '--message-type',
            type=str,
            default='channel_message',
            choices=['channel_message', 'dm', 'notification'],
            help='Type of message to send'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=1,
            help='Number of test messages to send'
        )
        parser.add_argument(
            '--channel-id',
            type=str,
            default='test_channel',
            help='Channel ID for the test message'
        )

    def handle(self, *args, **options):
        channel_layer = get_channel_layer()

        if not channel_layer:
            self.stdout.write(
                self.style.ERROR('Channel layer not configured. Please ensure Redis is running.')
            )
            return

        message_type = options['message_type']
        count = options['count']
        channel_id = options['channel_id']

        self.stdout.write(f'Sending {count} test {message_type} message(s)...')

        for i in range(count):
            if message_type == 'channel_message':
                self.send_channel_message(channel_layer, channel_id, i + 1)
            elif message_type == 'dm':
                self.send_dm_message(channel_layer, i + 1)
            elif message_type == 'notification':
                self.send_notification(channel_layer, i + 1)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully sent {count} test message(s)')
        )

    def send_channel_message(self, channel_layer, channel_id, msg_num):
        """Send a test channel message"""
        message_data = {
            'id': f'test_msg_{msg_num}',
            'channel_id': channel_id,
            'channel_name': f'test-channel',
            'channel_type': 'public_channel',
            'user_id': 'test_user_123',
            'text': f'Test message #{msg_num} from management command',
            'timestamp': str(timezone.now().timestamp()),
            'thread_ts': None,
            'is_thread_reply': False,
            'is_dm': False,
            'workspace_id': 'test_workspace_1',
            'workspace_name': 'Test Workspace',
            'created_at': timezone.now().isoformat(),
            'event_type': 'test_channel_message'
        }

        # Send to all anonymous message groups
        groups = [
            'slack_messages_anonymous',
            f'workspace_test_workspace_1_anonymous',
            f'channel_{channel_id}_anonymous',
        ]

        for group in groups:
            try:
                async_to_sync(channel_layer.group_send)(group, {
                    'type': 'slack_channel_message',
                    'message': message_data
                })
                self.stdout.write(f'  [OK] Sent to group: {group}')
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'  [ERROR] Failed to send to {group}: {str(e)}')
                )

    def send_dm_message(self, channel_layer, msg_num):
        """Send a test DM message"""
        message_data = {
            'id': f'test_dm_{msg_num}',
            'channel_id': f'D123456{msg_num:03d}',
            'channel_name': None,
            'channel_type': 'im',
            'user_id': 'test_user_456',
            'text': f'Test DM #{msg_num} from management command',
            'timestamp': str(timezone.now().timestamp()),
            'thread_ts': None,
            'is_thread_reply': False,
            'is_dm': True,
            'workspace_id': 'test_workspace_1',
            'workspace_name': 'Test Workspace',
            'created_at': timezone.now().isoformat(),
            'event_type': 'test_dm'
        }

        groups = [
            'slack_messages_anonymous',
            'workspace_test_workspace_1_anonymous',
        ]

        for group in groups:
            try:
                async_to_sync(channel_layer.group_send)(group, {
                    'type': 'slack_dm',
                    'message': message_data
                })
                self.stdout.write(f'  [OK] Sent DM to group: {group}')
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'  [ERROR] Failed to send DM to {group}: {str(e)}')
                )

    def send_notification(self, channel_layer, msg_num):
        """Send a test notification"""
        notification_data = {
            'type': 'test_notification',
            'data': {
                'message': f'Test notification #{msg_num}',
                'timestamp': timezone.now().isoformat(),
                'source': 'management_command',
                'event_type': 'test_notification'
            }
        }

        group = 'slack_notifications_anonymous'

        try:
            async_to_sync(channel_layer.group_send)(group, {
                'type': 'slack_notification',
                'notification': notification_data
            })
            self.stdout.write(f'  [OK] Sent notification to group: {group}')
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'  [ERROR] Failed to send notification to {group}: {str(e)}')
            )