"""
Direct Message monitoring using Slack Conversations API
Requires user-level OAuth tokens with conversations:read scope
"""
import asyncio
import time
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class SlackDMMonitor:
    def __init__(self, user_token):
        """
        Initialize DM monitor with user-level token
        Requires scopes: conversations:read, conversations:history, users:read
        """
        self.client = WebClient(token=user_token)
        self.last_check = time.time()
        self.monitored_conversations = {}

    async def get_dm_conversations(self):
        """Get list of direct message conversations"""
        try:
            response = self.client.conversations_list(
                types="im",  # Direct messages only
                limit=200
            )
            return response["channels"]
        except SlackApiError as e:
            logger.error(f"Error fetching DM conversations: {e}")
            return []

    async def get_recent_messages(self, channel_id, since_timestamp):
        """Get messages from a conversation since timestamp"""
        try:
            response = self.client.conversations_history(
                channel=channel_id,
                oldest=str(since_timestamp),
                limit=100
            )
            return response["messages"]
        except SlackApiError as e:
            logger.error(f"Error fetching messages from {channel_id}: {e}")
            return []

    async def monitor_dms(self, interval=30):
        """
        Poll for new direct messages
        interval: seconds between checks
        """
        logger.info(f"Starting DM monitoring with {interval}s interval")

        while True:
            try:
                current_time = time.time()
                conversations = await self.get_dm_conversations()

                for conv in conversations:
                    channel_id = conv["id"]

                    # Get messages since last check
                    messages = await self.get_recent_messages(
                        channel_id,
                        self.last_check
                    )

                    # Process new messages
                    for message in reversed(messages):  # Oldest first
                        if float(message.get("ts", 0)) > self.last_check:
                            await self.process_dm_message(message, channel_id)

                self.last_check = current_time
                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Error in DM monitoring loop: {e}")
                await asyncio.sleep(interval)

    async def process_dm_message(self, message, channel_id):
        """Process a direct message"""
        try:
            # Get user info
            user_id = message.get("user")
            if user_id:
                user_info = self.client.users_info(user=user_id)
                username = user_info["user"]["name"]
            else:
                username = "Unknown"

            # Log the message
            text = message.get("text", "")
            timestamp = message.get("ts", "")

            logger.info(f"DM from {username}: {text}")

            # Broadcast to WebSocket (same as webhook events)
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            if channel_layer:
                await channel_layer.group_send(
                    'slack_messages',
                    {
                        'type': 'slack_message',
                        'message': {
                            'type': 'direct_message',
                            'user': username,
                            'text': text,
                            'timestamp': timestamp,
                            'channel': channel_id,
                            'source': 'dm_monitor'
                        }
                    }
                )

        except Exception as e:
            logger.error(f"Error processing DM message: {e}")

# Django management command integration
if __name__ == "__main__":
    # Example usage with user token
    USER_TOKEN = "xoxp-your-user-token-here"
    monitor = SlackDMMonitor(USER_TOKEN)
    asyncio.run(monitor.monitor_dms(interval=30))