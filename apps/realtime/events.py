import logging
import asyncio
from datetime import datetime
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings
from apps.core.models import SlackWorkspace, SlackUser, SlackChannel, SlackMessage, SlackBot

logger = logging.getLogger('slack_api')


class SlackEventHandler:
    """
    Handler for processing Slack Events API callbacks
    """

    def __init__(self, app_config=None):
        self.app_config = app_config
        self.channel_layer = get_channel_layer()

    async def handle_event(self, event, team_id, api_app_id):
        """
        Main event handler that routes to specific event processors
        """
        try:
            event_type = event.get('type')
            logger.info(f"Processing Slack event: {event_type} from team {team_id}")

            # Route to specific handlers
            if event_type == 'message':
                return await self.handle_message_event(event, team_id)
            elif event_type == 'app_mention':
                return await self.handle_app_mention_event(event, team_id)
            elif event_type == 'member_joined_channel':
                return await self.handle_member_joined_event(event, team_id)
            elif event_type == 'member_left_channel':
                return await self.handle_member_left_event(event, team_id)
            elif event_type == 'channel_created':
                return await self.handle_channel_created_event(event, team_id)
            elif event_type == 'channel_deleted':
                return await self.handle_channel_deleted_event(event, team_id)
            elif event_type == 'channel_rename':
                return await self.handle_channel_rename_event(event, team_id)
            elif event_type == 'reaction_added':
                return await self.handle_reaction_added_event(event, team_id)
            elif event_type == 'reaction_removed':
                return await self.handle_reaction_removed_event(event, team_id)
            else:
                logger.warning(f"Unhandled event type: {event_type}")
                return {'success': True, 'message': f'Unhandled event type: {event_type}'}

        except Exception as e:
            logger.error(f"Error handling Slack event {event.get('type')}: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_message_event(self, event, team_id):
        """
        Handle message events (channels, DMs, threads)
        """
        try:
            # Extract message data
            channel_id = event.get('channel')
            user_id = event.get('user')
            text = event.get('text', '')
            ts = event.get('ts')
            thread_ts = event.get('thread_ts')
            message_type = event.get('subtype', 'message')

            # Skip bot messages and message changes to avoid loops
            if event.get('subtype') in ['bot_message', 'message_changed', 'message_deleted']:
                return {'success': True, 'message': 'Skipped bot/system message'}

            # Get workspace
            workspace = await self.get_workspace_by_team_id(team_id)
            if not workspace:
                logger.warning(f"Workspace not found for team {team_id}")
                return {'success': False, 'error': 'Workspace not found'}

            # Get or create channel
            channel = await self.get_or_create_channel(workspace, channel_id, event)

            # Get user if available
            slack_user = None
            if user_id:
                slack_user = await self.get_slack_user(workspace, user_id)

            # Store message in database
            message = await self.store_message(
                workspace, channel, slack_user, ts, text, message_type, thread_ts
            )

            # Determine message classification
            is_dm = channel.channel_type in ['im', 'mpim']

            # Prepare message data for broadcasting
            message_data = {
                'id': str(message.id),
                'channel_id': channel_id,
                'channel_name': channel.channel_name,
                'channel_type': channel.channel_type,
                'user_id': user_id,
                'text': text,
                'timestamp': ts,
                'thread_ts': thread_ts,
                'is_thread_reply': bool(thread_ts and thread_ts != ts),
                'is_dm': is_dm,
                'workspace_id': str(workspace.id),
                'workspace_name': workspace.team_name,
                'created_at': message.created_at.isoformat(),
                'event_type': 'message'
            }

            # Broadcast to WebSocket consumers
            await self.broadcast_message(message_data, workspace, channel, is_dm)

            logger.info(f"Processed message event: {ts} in {channel_id}")
            return {'success': True, 'message': 'Message processed successfully'}

        except Exception as e:
            logger.error(f"Error handling message event: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_app_mention_event(self, event, team_id):
        """
        Handle app mention events (@bot_name)
        """
        try:
            # Similar to message handling but specifically for mentions
            message_data = {
                'channel_id': event.get('channel'),
                'user_id': event.get('user'),
                'text': event.get('text', ''),
                'timestamp': event.get('ts'),
                'event_type': 'app_mention'
            }

            # Broadcast to all users in the workspace
            await self.broadcast_notification(
                message_data,
                team_id,
                notification_type='app_mention'
            )

            return {'success': True, 'message': 'App mention processed'}

        except Exception as e:
            logger.error(f"Error handling app mention: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_member_joined_event(self, event, team_id):
        """
        Handle member joined channel events
        """
        try:
            notification_data = {
                'channel_id': event.get('channel'),
                'user_id': event.get('user'),
                'timestamp': event.get('ts'),
                'event_type': 'member_joined',
                'message': f"User {event.get('user')} joined the channel"
            }

            await self.broadcast_notification(notification_data, team_id, 'member_activity')
            return {'success': True, 'message': 'Member joined event processed'}

        except Exception as e:
            logger.error(f"Error handling member joined: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_member_left_event(self, event, team_id):
        """
        Handle member left channel events
        """
        try:
            notification_data = {
                'channel_id': event.get('channel'),
                'user_id': event.get('user'),
                'timestamp': event.get('ts'),
                'event_type': 'member_left',
                'message': f"User {event.get('user')} left the channel"
            }

            await self.broadcast_notification(notification_data, team_id, 'member_activity')
            return {'success': True, 'message': 'Member left event processed'}

        except Exception as e:
            logger.error(f"Error handling member left: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_channel_created_event(self, event, team_id):
        """
        Handle channel created events
        """
        try:
            workspace = await self.get_workspace_by_team_id(team_id)
            if workspace:
                # Create the new channel in our database
                channel_info = event.get('channel', {})
                await self.get_or_create_channel(workspace, channel_info.get('id'), event)

            notification_data = {
                'channel_id': event.get('channel', {}).get('id'),
                'channel_name': event.get('channel', {}).get('name'),
                'creator': event.get('channel', {}).get('creator'),
                'timestamp': event.get('ts'),
                'event_type': 'channel_created'
            }

            await self.broadcast_notification(notification_data, team_id, 'channel_activity')
            return {'success': True, 'message': 'Channel created event processed'}

        except Exception as e:
            logger.error(f"Error handling channel created: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_channel_deleted_event(self, event, team_id):
        """
        Handle channel deleted events
        """
        try:
            workspace = await self.get_workspace_by_team_id(team_id)
            if workspace:
                # Mark channel as archived in our database
                try:
                    from asgiref.sync import sync_to_async
                    channel = await sync_to_async(SlackChannel.objects.get)(
                        workspace=workspace,
                        channel_id=event.get('channel')
                    )
                    channel.is_archived = True
                    await sync_to_async(channel.save)()
                except SlackChannel.DoesNotExist:
                    pass

            notification_data = {
                'channel_id': event.get('channel'),
                'timestamp': event.get('ts'),
                'event_type': 'channel_deleted'
            }

            await self.broadcast_notification(notification_data, team_id, 'channel_activity')
            return {'success': True, 'message': 'Channel deleted event processed'}

        except Exception as e:
            logger.error(f"Error handling channel deleted: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_channel_rename_event(self, event, team_id):
        """
        Handle channel rename events
        """
        try:
            workspace = await self.get_workspace_by_team_id(team_id)
            if workspace:
                # Update channel name in our database
                try:
                    from asgiref.sync import sync_to_async
                    channel = await sync_to_async(SlackChannel.objects.get)(
                        workspace=workspace,
                        channel_id=event.get('channel', {}).get('id')
                    )
                    channel.channel_name = event.get('channel', {}).get('name')
                    await sync_to_async(channel.save)()
                except SlackChannel.DoesNotExist:
                    pass

            notification_data = {
                'channel_id': event.get('channel', {}).get('id'),
                'old_name': event.get('channel', {}).get('name_normalized'),
                'new_name': event.get('channel', {}).get('name'),
                'timestamp': event.get('ts'),
                'event_type': 'channel_rename'
            }

            await self.broadcast_notification(notification_data, team_id, 'channel_activity')
            return {'success': True, 'message': 'Channel rename event processed'}

        except Exception as e:
            logger.error(f"Error handling channel rename: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_reaction_added_event(self, event, team_id):
        """
        Handle reaction added events
        """
        try:
            reaction_data = {
                'reaction': event.get('reaction'),
                'user_id': event.get('user'),
                'item_user': event.get('item_user'),
                'item': event.get('item', {}),
                'timestamp': event.get('event_ts'),
                'event_type': 'reaction_added'
            }

            await self.broadcast_notification(reaction_data, team_id, 'reaction')
            return {'success': True, 'message': 'Reaction added event processed'}

        except Exception as e:
            logger.error(f"Error handling reaction added: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_reaction_removed_event(self, event, team_id):
        """
        Handle reaction removed events
        """
        try:
            reaction_data = {
                'reaction': event.get('reaction'),
                'user_id': event.get('user'),
                'item_user': event.get('item_user'),
                'item': event.get('item', {}),
                'timestamp': event.get('event_ts'),
                'event_type': 'reaction_removed'
            }

            await self.broadcast_notification(reaction_data, team_id, 'reaction')
            return {'success': True, 'message': 'Reaction removed event processed'}

        except Exception as e:
            logger.error(f"Error handling reaction removed: {str(e)}")
            return {'success': False, 'error': str(e)}

    # Helper methods

    async def get_workspace_by_team_id(self, team_id):
        """Get workspace by Slack team ID"""
        try:
            from asgiref.sync import sync_to_async
            return await sync_to_async(SlackWorkspace.objects.get)(
                team_id=team_id,
                is_active=True
            )
        except SlackWorkspace.DoesNotExist:
            return None

    async def get_or_create_channel(self, workspace, channel_id, event):
        """Get or create channel from event data"""
        try:
            from asgiref.sync import sync_to_async

            # Try to get existing channel
            try:
                return await sync_to_async(SlackChannel.objects.get)(
                    workspace=workspace,
                    channel_id=channel_id
                )
            except SlackChannel.DoesNotExist:
                pass

            # Determine channel type from event or channel ID
            channel_type = 'public_channel'
            if channel_id.startswith('D'):
                channel_type = 'im'
            elif channel_id.startswith('G'):
                channel_type = 'private_channel'
            elif channel_id.startswith('C'):
                channel_type = 'public_channel'

            # Create new channel
            channel = await sync_to_async(SlackChannel.objects.create)(
                workspace=workspace,
                channel_id=channel_id,
                channel_name=f"channel_{channel_id}",  # Default name, can be updated later
                channel_type=channel_type,
                is_private=(channel_type in ['private_channel', 'im', 'mpim'])
            )

            logger.info(f"Created new channel: {channel_id} in workspace {workspace.team_name}")
            return channel

        except Exception as e:
            logger.error(f"Error getting/creating channel {channel_id}: {str(e)}")
            return None

    async def get_slack_user(self, workspace, user_id):
        """Get Slack user by ID"""
        try:
            from asgiref.sync import sync_to_async
            return await sync_to_async(SlackUser.objects.get)(
                workspace=workspace,
                slack_user_id=user_id,
                is_active=True
            )
        except SlackUser.DoesNotExist:
            return None

    async def store_message(self, workspace, channel, slack_user, ts, text, message_type, thread_ts=None):
        """Store message in database"""
        try:
            from asgiref.sync import sync_to_async

            message = await sync_to_async(SlackMessage.objects.create)(
                workspace=workspace,
                channel=channel,
                slack_user=slack_user,
                message_ts=ts,
                message_type=message_type,
                text=text,
                thread_ts=thread_ts,
                is_thread_reply=(thread_ts and thread_ts != ts)
            )

            return message

        except Exception as e:
            logger.error(f"Error storing message {ts}: {str(e)}")
            return None

    async def broadcast_message(self, message_data, workspace, channel, is_dm=False):
        """Broadcast message to WebSocket consumers"""
        try:
            if not settings.REALTIME_SETTINGS.get('MESSAGE_BROADCAST_ENABLED', True):
                return

            # Determine the appropriate WebSocket groups to broadcast to
            groups = []

            if is_dm:
                # For DMs, broadcast to specific user groups
                groups.extend([
                    f"slack_messages_anonymous",  # For testing
                    f"workspace_{workspace.id}_anonymous",
                ])
            else:
                # For channel messages, broadcast to channel and workspace groups
                groups.extend([
                    f"slack_messages_anonymous",  # For testing
                    f"workspace_{workspace.id}_anonymous",
                    f"channel_{channel.channel_id}_anonymous",
                ])

            # Broadcast to all relevant groups
            for group in groups:
                try:
                    await self.channel_layer.group_send(group, {
                        'type': 'slack_channel_message' if not is_dm else 'slack_dm',
                        'message': message_data
                    })
                except Exception as e:
                    logger.error(f"Error sending to group {group}: {str(e)}")

            logger.info(f"Broadcasted message to {len(groups)} WebSocket groups")

        except Exception as e:
            logger.error(f"Error broadcasting message: {str(e)}")

    async def broadcast_notification(self, notification_data, team_id, notification_type):
        """Broadcast general notifications to WebSocket consumers"""
        try:
            groups = [
                f"slack_notifications_anonymous",  # For testing
                f"team_{team_id}_notifications_anonymous",
            ]

            for group in groups:
                try:
                    await self.channel_layer.group_send(group, {
                        'type': 'slack_notification',
                        'notification': {
                            'type': notification_type,
                            'data': notification_data,
                            'timestamp': datetime.now().isoformat()
                        }
                    })
                except Exception as e:
                    logger.error(f"Error sending notification to group {group}: {str(e)}")

        except Exception as e:
            logger.error(f"Error broadcasting notification: {str(e)}")


# Sync wrapper for use in sync contexts
def handle_slack_event_sync(event, team_id, api_app_id, app_config=None):
    """
    Synchronous wrapper for handling Slack events
    """
    handler = SlackEventHandler(app_config)
    return async_to_sync(handler.handle_event)(event, team_id, api_app_id)