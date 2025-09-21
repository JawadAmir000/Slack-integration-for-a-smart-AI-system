import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class SlackMessageConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time Slack message delivery
    """

    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Get user from authentication
            self.user = self.scope["user"]

            if self.user.is_anonymous:
                # For development, we'll allow anonymous connections
                # In production, you might want to reject these
                self.user_id = "anonymous"
                logger.warning("Anonymous WebSocket connection accepted")
            else:
                self.user_id = str(self.user.id)
                logger.info(f"Authenticated WebSocket connection for user {self.user_id}")

            # Join the main anonymous group that receives all messages from Slack Events
            self.room_group_name = "slack_messages_anonymous"

            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            await self.accept()

            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to real-time Slack messages',
                'user_id': self.user_id,
                'timestamp': self.get_timestamp()
            }))

            logger.info(f"WebSocket connection established for user {self.user_id}")

        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Leave room group
            if hasattr(self, 'room_group_name'):
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
            logger.info(f"WebSocket disconnected for user {getattr(self, 'user_id', 'unknown')} (code: {close_code})")
        except Exception as e:
            logger.error(f"WebSocket disconnect error: {str(e)}")

    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')

            if message_type == 'ping':
                # Handle ping/pong for connection health
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': self.get_timestamp()
                }))
            elif message_type == 'subscribe':
                # Handle subscription to specific channels/workspaces
                await self.handle_subscription(text_data_json)
            else:
                logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            logger.error("Invalid JSON received from WebSocket")
        except Exception as e:
            logger.error(f"WebSocket receive error: {str(e)}")

    async def handle_subscription(self, data):
        """Handle subscription to specific Slack channels or workspaces"""
        try:
            workspace_id = data.get('workspace_id')
            channel_id = data.get('channel_id')

            if workspace_id:
                # Subscribe to workspace messages
                workspace_group = f"workspace_{workspace_id}_{self.user_id}"
                await self.channel_layer.group_add(workspace_group, self.channel_name)

                await self.send(text_data=json.dumps({
                    'type': 'subscription_confirmed',
                    'workspace_id': workspace_id,
                    'message': f'Subscribed to workspace {workspace_id}',
                    'timestamp': self.get_timestamp()
                }))

            if channel_id:
                # Subscribe to specific channel messages
                channel_group = f"channel_{channel_id}_{self.user_id}"
                await self.channel_layer.group_add(channel_group, self.channel_name)

                await self.send(text_data=json.dumps({
                    'type': 'subscription_confirmed',
                    'channel_id': channel_id,
                    'message': f'Subscribed to channel {channel_id}',
                    'timestamp': self.get_timestamp()
                }))

        except Exception as e:
            logger.error(f"Subscription handling error: {str(e)}")

    # Enhanced group message handlers (called by channel layer)

    async def slack_message(self, event):
        """Send Slack message to WebSocket with enhanced data"""
        await self.send(text_data=json.dumps({
            'type': 'slack_message',
            'message': event['message'],
            'timestamp': self.get_timestamp(),
            'delivery_time': self.get_timestamp()
        }))

    async def slack_dm(self, event):
        """Send Slack direct message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'slack_dm',
            'message': event['message'],
            'timestamp': self.get_timestamp(),
            'delivery_time': self.get_timestamp()
        }))

    async def slack_channel_message(self, event):
        """Send Slack channel message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'slack_channel_message',
            'message': event['message'],
            'timestamp': self.get_timestamp(),
            'delivery_time': self.get_timestamp()
        }))

    async def message_broadcast(self, event):
        """Handle general message broadcast"""
        await self.send(text_data=json.dumps({
            'type': 'broadcast',
            'message': event['message'],
            'timestamp': self.get_timestamp(),
            'delivery_time': self.get_timestamp()
        }))

    async def typing_indicator(self, event):
        """Handle typing indicator events"""
        await self.send(text_data=json.dumps({
            'type': 'typing_indicator',
            'data': event['data'],
            'timestamp': self.get_timestamp()
        }))

    async def slack_reaction(self, event):
        """Handle reaction events (added/removed)"""
        await self.send(text_data=json.dumps({
            'type': 'slack_reaction',
            'reaction': event.get('reaction', {}),
            'timestamp': self.get_timestamp()
        }))

    async def slack_presence(self, event):
        """Handle user presence updates"""
        await self.send(text_data=json.dumps({
            'type': 'slack_presence',
            'presence': event.get('presence', {}),
            'timestamp': self.get_timestamp()
        }))

    async def slack_file_shared(self, event):
        """Handle file sharing events"""
        await self.send(text_data=json.dumps({
            'type': 'slack_file_shared',
            'file': event.get('file', {}),
            'timestamp': self.get_timestamp()
        }))

    @staticmethod
    def get_timestamp():
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.now().isoformat()

    @database_sync_to_async
    def get_user_workspaces(self, user):
        """Get user's Slack workspaces"""
        try:
            from apps.core.models import SlackUser
            slack_users = SlackUser.objects.filter(user=user, is_active=True)
            return [su.workspace.id for su in slack_users]
        except Exception as e:
            logger.error(f"Error getting user workspaces: {str(e)}")
            return []


class SlackNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for general Slack notifications and status updates
    """

    async def connect(self):
        """Handle WebSocket connection for notifications"""
        try:
            self.user = self.scope["user"]

            if self.user.is_anonymous:
                self.user_id = "anonymous"
            else:
                self.user_id = str(self.user.id)

            # Join the main anonymous notifications group that receives all notifications from Slack Events
            self.notification_group = "slack_notifications_anonymous"
            await self.channel_layer.group_add(
                self.notification_group,
                self.channel_name
            )

            await self.accept()

            await self.send(text_data=json.dumps({
                'type': 'notification_connection',
                'message': 'Connected to Slack notifications',
                'timestamp': SlackMessageConsumer.get_timestamp()
            }))

        except Exception as e:
            logger.error(f"Notification WebSocket connection error: {str(e)}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            if hasattr(self, 'notification_group'):
                await self.channel_layer.group_discard(
                    self.notification_group,
                    self.channel_name
                )
        except Exception as e:
            logger.error(f"Notification WebSocket disconnect error: {str(e)}")

    async def receive(self, text_data):
        """Handle notification preferences and commands"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'set_preferences':
                await self.handle_notification_preferences(data)

        except Exception as e:
            logger.error(f"Notification receive error: {str(e)}")

    async def handle_notification_preferences(self, data):
        """Handle user notification preferences"""
        # Implement notification preference handling
        await self.send(text_data=json.dumps({
            'type': 'preferences_updated',
            'message': 'Notification preferences updated',
            'timestamp': SlackMessageConsumer.get_timestamp()
        }))

    async def slack_notification(self, event):
        """Send enhanced notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification'],
            'timestamp': SlackMessageConsumer.get_timestamp(),
            'delivery_time': SlackMessageConsumer.get_timestamp()
        }))

    async def slack_status(self, event):
        """Send status update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'status': event['status'],
            'timestamp': SlackMessageConsumer.get_timestamp(),
            'delivery_time': SlackMessageConsumer.get_timestamp()
        }))

    async def typing_indicator(self, event):
        """Handle typing indicators in notification consumer"""
        await self.send(text_data=json.dumps({
            'type': 'typing_indicator',
            'data': event['data'],
            'timestamp': SlackMessageConsumer.get_timestamp()
        }))

    async def presence_update(self, event):
        """Handle presence updates in notification consumer"""
        await self.send(text_data=json.dumps({
            'type': 'presence_update',
            'data': event['data'],
            'timestamp': SlackMessageConsumer.get_timestamp()
        }))