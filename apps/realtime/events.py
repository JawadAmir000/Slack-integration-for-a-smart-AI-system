import logging
import asyncio
from datetime import datetime
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings
from apps.core.models import SlackWorkspace, SlackUser, SlackChannel, SlackMessage, SlackBot
from .error_handling import (
    with_error_handling, SlackEventError, ErrorTracker,
    PerformanceMonitor, handle_critical_error, safe_json_serialize
)
from .logging_config import log_slack_event, log_performance_metric

logger = logging.getLogger('slack_realtime')


class SlackEventHandler:
    """
    Handler for processing Slack Events API callbacks
    """

    def __init__(self, app_config=None):
        self.app_config = app_config
        self.channel_layer = get_channel_layer()

    @with_error_handling(max_retries=2, retry_delay=0.5)
    async def handle_event(self, event, team_id, api_app_id):
        """
        Enhanced main event handler that routes to specific event processors
        """
        event_type = event.get('type')
        event_subtype = event.get('subtype')

        # Log event with structured context
        log_slack_event(logger, event_type, team_id, event.get('channel'),
                       f"Processing event (subtype: {event_subtype})")

        # Enhanced event routing with performance tracking
        start_time = asyncio.get_event_loop().time()

        # Track message latency if timestamp is available
        if event.get('ts'):
            PerformanceMonitor.track_message_latency(event.get('ts'), start_time)

        try:
            # Route to specific handlers
            if event_type == 'message':
                result = await self.handle_message_event(event, team_id)
            elif event_type == 'app_mention':
                result = await self.handle_app_mention_event(event, team_id)
            elif event_type == 'member_joined_channel':
                result = await self.handle_member_joined_event(event, team_id)
            elif event_type == 'member_left_channel':
                result = await self.handle_member_left_event(event, team_id)
            elif event_type == 'channel_created':
                result = await self.handle_channel_created_event(event, team_id)
            elif event_type == 'channel_deleted':
                result = await self.handle_channel_deleted_event(event, team_id)
            elif event_type == 'channel_rename':
                result = await self.handle_channel_rename_event(event, team_id)
            elif event_type == 'reaction_added':
                result = await self.handle_reaction_added_event(event, team_id)
            elif event_type == 'reaction_removed':
                result = await self.handle_reaction_removed_event(event, team_id)
            elif event_type == 'user_typing':
                result = await self.handle_user_typing_event(event, team_id)
            elif event_type == 'presence_change':
                result = await self.handle_presence_change_event(event, team_id)
            elif event_type == 'file_shared':
                result = await self.handle_file_shared_event(event, team_id)
            elif event_type == 'team_join':
                result = await self.handle_team_join_event(event, team_id)
            else:
                logger.warning(f"Unhandled event type: {event_type}")
                result = {'success': True, 'message': f'Unhandled event type: {event_type}'}

            # Log processing time for performance monitoring
            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
            log_performance_metric(logger, f"handle_{event_type}_event", processing_time, event_type, team_id)

            # Record success metrics
            if result.get('success'):
                logger.debug(f"Successfully processed {event_type} event")
            else:
                ErrorTracker.record_error(f"EVENT_PROCESSING_{event_type.upper()}",
                                        context={'team_id': team_id, 'event': event},
                                        team_id=team_id)

            return result

        except Exception as e:
            handle_critical_error(e, context={
                'event_type': event_type,
                'team_id': team_id,
                'event': safe_json_serialize(event)
            })
            raise SlackEventError(str(e), event_type=event_type, team_id=team_id)

    @with_error_handling(event_type='message', max_retries=1)
    async def handle_message_event(self, event, team_id):
        """
        Enhanced message event handler with support for all message types
        """
        try:
            # Extract message data
            channel_id = event.get('channel')
            user_id = event.get('user')
            text = event.get('text', '')
            ts = event.get('ts')
            thread_ts = event.get('thread_ts')
            message_type = event.get('subtype', 'message')
            files = event.get('files', [])
            attachments = event.get('attachments', [])
            edited = event.get('edited')

            # Enhanced filtering - skip certain message types to avoid loops
            skip_subtypes = [
                'bot_message', 'message_changed', 'message_deleted',
                'channel_join', 'channel_leave', 'channel_topic',
                'channel_purpose', 'channel_name', 'channel_archive',
                'channel_unarchive', 'group_join', 'group_leave'
            ]

            if message_type in skip_subtypes:
                logger.debug(f"Skipping message with subtype: {message_type}")
                return {'success': True, 'message': f'Skipped message subtype: {message_type}'}

            # Get workspace
            workspace = await self.get_workspace_by_team_id(team_id)
            if not workspace:
                logger.warning(f"Workspace not found for team {team_id}")
                return {'success': False, 'error': 'Workspace not found'}

            # Get or create channel
            channel = await self.get_or_create_channel(workspace, channel_id, event)
            if not channel:
                logger.error(f"Failed to get/create channel: {channel_id}")
                return {'success': False, 'error': 'Channel creation failed'}

            # Get user if available
            slack_user = None
            if user_id:
                slack_user = await self.get_slack_user(workspace, user_id)

            # Store message in database
            message = await self.store_message(
                workspace, channel, slack_user, ts, text, message_type, thread_ts
            )

            if not message:
                logger.error(f"Failed to store message: {ts}")
                return {'success': False, 'error': 'Message storage failed'}

            # Determine message classification
            is_dm = channel.channel_type in ['im', 'mpim']
            is_thread = bool(thread_ts and thread_ts != ts)

            # Enhanced message data for broadcasting
            message_data = {
                'id': str(message.id),
                'channel_id': channel_id,
                'channel_name': channel.channel_name,
                'channel_type': channel.channel_type,
                'user_id': user_id,
                'text': text,
                'timestamp': ts,
                'thread_ts': thread_ts,
                'is_thread_reply': is_thread,
                'is_dm': is_dm,
                'message_type': message_type,
                'workspace_id': str(workspace.id),
                'workspace_name': workspace.team_name,
                'created_at': message.created_at.isoformat(),
                'event_type': 'message',
                'has_files': bool(files),
                'has_attachments': bool(attachments),
                'is_edited': bool(edited),
                'files_count': len(files),
                'processing_time': asyncio.get_event_loop().time()
            }

            # Add file information if present
            if files:
                message_data['files'] = [{
                    'id': f.get('id'),
                    'name': f.get('name'),
                    'filetype': f.get('filetype'),
                    'url_private': f.get('url_private'),
                    'permalink': f.get('permalink')
                } for f in files[:5]]  # Limit to first 5 files

            # Broadcast to WebSocket consumers with optimized routing
            await self.broadcast_message(message_data, workspace, channel, is_dm)

            logger.info(f"Processed message event: {ts} in {channel_id} (type: {message_type}, thread: {is_thread})")
            return {'success': True, 'message': 'Message processed successfully'}

        except Exception as e:
            logger.error(f"Error handling message event: {str(e)}", exc_info=True)
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

    async def handle_user_typing_event(self, event, team_id):
        """
        Handle user typing events for real-time typing indicators
        """
        try:
            typing_data = {
                'channel_id': event.get('channel'),
                'user_id': event.get('user'),
                'timestamp': event.get('ts'),
                'event_type': 'user_typing'
            }

            # Broadcast typing indicator to channel subscribers
            await self.broadcast_typing_indicator(typing_data, team_id)
            return {'success': True, 'message': 'Typing event processed'}

        except Exception as e:
            logger.error(f"Error handling typing event: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_presence_change_event(self, event, team_id):
        """
        Handle user presence change events (online/away/active)
        """
        try:
            presence_data = {
                'user_id': event.get('user'),
                'presence': event.get('presence'),  # active, away, or offline
                'timestamp': event.get('ts'),
                'event_type': 'presence_change'
            }

            await self.broadcast_notification(presence_data, team_id, 'presence')
            return {'success': True, 'message': 'Presence change event processed'}

        except Exception as e:
            logger.error(f"Error handling presence change: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_file_shared_event(self, event, team_id):
        """
        Handle file shared events
        """
        try:
            file_data = {
                'file_id': event.get('file_id'),
                'user_id': event.get('user_id'),
                'channel_id': event.get('channel_id'),
                'timestamp': event.get('ts'),
                'event_type': 'file_shared'
            }

            await self.broadcast_notification(file_data, team_id, 'file_activity')
            return {'success': True, 'message': 'File shared event processed'}

        except Exception as e:
            logger.error(f"Error handling file shared: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def handle_team_join_event(self, event, team_id):
        """
        Handle new team member join events
        """
        try:
            user_info = event.get('user', {})
            join_data = {
                'user_id': user_info.get('id'),
                'user_name': user_info.get('name'),
                'real_name': user_info.get('real_name'),
                'timestamp': event.get('ts'),
                'event_type': 'team_join'
            }

            # Store new user in database if needed
            workspace = await self.get_workspace_by_team_id(team_id)
            if workspace:
                await self.get_or_create_slack_user(workspace, user_info)

            await self.broadcast_notification(join_data, team_id, 'team_activity')
            return {'success': True, 'message': 'Team join event processed'}

        except Exception as e:
            logger.error(f"Error handling team join: {str(e)}")
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
                is_thread_reply=bool(thread_ts and thread_ts != ts)
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
        """Enhanced notification broadcasting with optimized routing"""
        try:
            groups = [
                f"slack_notifications_anonymous",  # For testing
                f"team_{team_id}_notifications_anonymous",
            ]

            # Add channel-specific group if channel_id is present
            if notification_data.get('channel_id'):
                groups.append(f"channel_{notification_data['channel_id']}_notifications_anonymous")

            broadcast_data = {
                'type': 'slack_notification',
                'notification': {
                    'type': notification_type,
                    'data': notification_data,
                    'timestamp': datetime.now().isoformat(),
                    'team_id': team_id
                }
            }

            # Broadcast to all groups concurrently for better performance
            tasks = []
            for group in groups:
                task = self.channel_layer.group_send(group, broadcast_data)
                tasks.append(task)

            # Wait for all broadcasts to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log any errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error sending notification to group {groups[i]}: {str(result)}")

            logger.debug(f"Broadcasted {notification_type} notification to {len(groups)} groups")

        except Exception as e:
            logger.error(f"Error broadcasting notification: {str(e)}")

    async def broadcast_typing_indicator(self, typing_data, team_id):
        """Broadcast typing indicators to channel subscribers"""
        try:
            channel_id = typing_data.get('channel_id')
            if not channel_id:
                return

            groups = [
                f"channel_{channel_id}_anonymous",
                f"workspace_{team_id}_anonymous",
            ]

            broadcast_data = {
                'type': 'typing_indicator',
                'data': typing_data
            }

            # Broadcast concurrently
            tasks = [self.channel_layer.group_send(group, broadcast_data) for group in groups]
            await asyncio.gather(*tasks, return_exceptions=True)

            logger.debug(f"Broadcasted typing indicator for channel {channel_id}")

        except Exception as e:
            logger.error(f"Error broadcasting typing indicator: {str(e)}")

    async def get_or_create_slack_user(self, workspace, user_info):
        """Get or create Slack user from user info"""
        try:
            from asgiref.sync import sync_to_async

            user_id = user_info.get('id')
            if not user_id:
                return None

            # Try to get existing user
            try:
                return await sync_to_async(SlackUser.objects.get)(
                    workspace=workspace,
                    slack_user_id=user_id
                )
            except SlackUser.DoesNotExist:
                pass

            # Create new user
            user = await sync_to_async(SlackUser.objects.create)(
                workspace=workspace,
                slack_user_id=user_id,
                username=user_info.get('name', ''),
                real_name=user_info.get('real_name', ''),
                email=user_info.get('profile', {}).get('email', ''),
                is_admin=user_info.get('is_admin', False),
                is_bot=user_info.get('is_bot', False),
                is_active=not user_info.get('deleted', False)
            )

            logger.info(f"Created new Slack user: {user_id} in workspace {workspace.team_name}")
            return user

        except Exception as e:
            logger.error(f"Error creating Slack user {user_info.get('id')}: {str(e)}")
            return None


# Sync wrapper for use in sync contexts
def handle_slack_event_sync(event, team_id, api_app_id, app_config=None):
    """
    Synchronous wrapper for handling Slack events
    """
    handler = SlackEventHandler(app_config)
    return async_to_sync(handler.handle_event)(event, team_id, api_app_id)