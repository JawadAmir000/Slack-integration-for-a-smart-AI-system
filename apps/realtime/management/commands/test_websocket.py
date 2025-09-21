from django.core.management.base import BaseCommand
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import time


class Command(BaseCommand):
    help = 'Test WebSocket broadcasting with a simulated Slack message'

    def add_arguments(self, parser):
        parser.add_argument(
            '--message-type',
            type=str,
            default='direct_message',
            help='Type of message to simulate (direct_message, channel_message, notification)'
        )

    def handle(self, *args, **options):
        self.stdout.write('Testing WebSocket broadcasting...')

        channel_layer = get_channel_layer()
        if not channel_layer:
            self.stdout.write(
                self.style.ERROR('Channel layer not configured!')
            )
            return

        message_type = options['message_type']

        # Create test message based on type
        if message_type == 'direct_message':
            test_message = {
                'type': 'slack_dm',
                'message': {
                    'user_id': 'U12345TEST',
                    'text': 'This is a test direct message!',
                    'channel_id': 'D12345TEST',
                    'timestamp': str(time.time()),
                    'processing_time': time.time()
                }
            }
        elif message_type == 'channel_message':
            test_message = {
                'type': 'slack_channel_message',
                'message': {
                    'user_id': 'U12345TEST',
                    'text': 'This is a test channel message!',
                    'channel_id': 'C12345TEST',
                    'channel_name': 'general',
                    'timestamp': str(time.time()),
                    'processing_time': time.time()
                }
            }
        elif message_type == 'notification':
            test_message = {
                'type': 'notification',
                'notification': {
                    'title': 'Test Notification',
                    'message': 'This is a test notification!',
                    'timestamp': str(time.time())
                }
            }
        else:
            self.stdout.write(
                self.style.ERROR(f'Unknown message type: {message_type}')
            )
            return

        # Send to message WebSocket group
        try:
            async_to_sync(channel_layer.group_send)(
                'slack_messages',
                {
                    'type': 'slack_message',
                    'data': test_message
                }
            )
            self.stdout.write(
                self.style.SUCCESS(f'SUCCESS: Sent {message_type} to slack_messages group')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'ERROR: Failed to send to slack_messages: {e}')
            )

        # Send to notification WebSocket group if it's a notification
        if message_type == 'notification':
            try:
                async_to_sync(channel_layer.group_send)(
                    'slack_notifications',
                    {
                        'type': 'slack_notification',
                        'data': test_message
                    }
                )
                self.stdout.write(
                    self.style.SUCCESS(f'SUCCESS: Sent notification to slack_notifications group')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'ERROR: Failed to send to slack_notifications: {e}')
                )

        self.stdout.write(
            self.style.SUCCESS('SUCCESS: Test messages sent! Check your WebSocket client.')
        )
        self.stdout.write('INFO: Connect to:')
        self.stdout.write('   Messages: ws://localhost:8000/ws/slack/messages/')
        self.stdout.write('   Notifications: ws://localhost:8000/ws/slack/notifications/')