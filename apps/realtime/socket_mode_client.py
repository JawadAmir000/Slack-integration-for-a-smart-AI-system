"""
Slack Socket Mode client for real-time DM monitoring
Requires Socket Mode enabled in Slack app settings
"""
import asyncio
import logging
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from django.conf import settings
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

class SlackSocketModeClient:
    def __init__(self, app_token, bot_token):
        """
        Initialize Socket Mode client
        app_token: App-level token (xapp-1-...)
        bot_token: Bot user OAuth token (xoxb-...)
        """
        self.app = AsyncApp(token=bot_token)
        self.handler = AsyncSocketModeHandler(self.app, app_token)
        self.channel_layer = get_channel_layer()

        # Register event listeners
        self.register_events()

    def register_events(self):
        """Register event handlers for different message types"""

        @self.app.event("message")
        async def handle_message_events(event, say, logger):
            """Handle all message events including DMs"""
            try:
                # Check if it's a DM (channel starts with 'D')
                channel = event.get("channel", "")
                if channel.startswith("D"):
                    await self.process_dm(event)
                else:
                    await self.process_channel_message(event)

            except Exception as e:
                logger.error(f"Error handling message event: {e}")

        @self.app.event("member_joined_channel")
        async def handle_member_joined(event, logger):
            """Handle when someone joins a channel"""
            logger.info(f"Member joined channel: {event}")

        @self.app.event("app_mention")
        async def handle_app_mention(event, say, logger):
            """Handle when bot is mentioned"""
            logger.info(f"Bot mentioned: {event}")

    async def process_dm(self, event):
        """Process direct message"""
        try:
            user = event.get("user", "")
            text = event.get("text", "")
            ts = event.get("ts", "")
            channel = event.get("channel", "")

            # Get user info
            try:
                user_info = await self.app.client.users_info(user=user)
                username = user_info["user"]["name"]
                real_name = user_info["user"].get("real_name", username)
            except:
                username = user
                real_name = user

            logger.info(f"Socket Mode DM from {username} ({real_name}): {text}")

            # Broadcast to WebSocket
            if self.channel_layer:
                await self.channel_layer.group_send(
                    'slack_messages',
                    {
                        'type': 'slack_message',
                        'message': {
                            'type': 'direct_message',
                            'user': username,
                            'real_name': real_name,
                            'text': text,
                            'timestamp': ts,
                            'channel': channel,
                            'source': 'socket_mode'
                        }
                    }
                )

        except Exception as e:
            logger.error(f"Error processing DM via Socket Mode: {e}")

    async def process_channel_message(self, event):
        """Process channel message"""
        try:
            user = event.get("user", "")
            text = event.get("text", "")
            ts = event.get("ts", "")
            channel = event.get("channel", "")

            # Get channel info
            try:
                channel_info = await self.app.client.conversations_info(channel=channel)
                channel_name = channel_info["channel"]["name"]
            except:
                channel_name = channel

            # Get user info
            try:
                user_info = await self.app.client.users_info(user=user)
                username = user_info["user"]["name"]
            except:
                username = user

            logger.info(f"Socket Mode Channel message in #{channel_name} from {username}: {text}")

            # Broadcast to WebSocket
            if self.channel_layer:
                await self.channel_layer.group_send(
                    'slack_messages',
                    {
                        'type': 'slack_message',
                        'message': {
                            'type': 'channel_message',
                            'user': username,
                            'text': text,
                            'timestamp': ts,
                            'channel': channel_name,
                            'source': 'socket_mode'
                        }
                    }
                )

        except Exception as e:
            logger.error(f"Error processing channel message via Socket Mode: {e}")

    async def start(self):
        """Start the Socket Mode client"""
        logger.info("Starting Slack Socket Mode client...")
        await self.handler.start_async()

    async def close(self):
        """Close the Socket Mode client"""
        logger.info("Closing Slack Socket Mode client...")
        await self.handler.close_async()

# Django management command integration
async def start_socket_mode_client():
    """Start Socket Mode client with tokens from settings"""
    try:
        # These need to be configured in your Slack app
        app_token = getattr(settings, 'SLACK_APP_TOKEN', None)  # xapp-1-...
        bot_token = getattr(settings, 'SLACK_BOT_TOKEN', None)  # xoxb-...

        if not app_token or not bot_token:
            logger.error("Missing SLACK_APP_TOKEN or SLACK_BOT_TOKEN in settings")
            return

        client = SlackSocketModeClient(app_token, bot_token)
        await client.start()

    except Exception as e:
        logger.error(f"Error starting Socket Mode client: {e}")

if __name__ == "__main__":
    # Example usage
    asyncio.run(start_socket_mode_client())