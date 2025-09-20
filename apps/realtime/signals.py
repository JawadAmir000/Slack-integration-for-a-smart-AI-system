from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.core.models import SlackMessage, SlackChannel, SlackWorkspace
import logging

logger = logging.getLogger('realtime')
channel_layer = get_channel_layer()


@receiver(post_save, sender=SlackMessage)
def handle_message_created(sender, instance, created, **kwargs):
    """
    Handle new messages created in the database
    (This can be triggered from API calls or other sources)
    """
    if created and channel_layer:
        try:
            # Prepare message data
            message_data = {
                'id': str(instance.id),
                'channel_id': instance.channel.channel_id,
                'channel_name': instance.channel.channel_name,
                'channel_type': instance.channel.channel_type,
                'workspace_id': str(instance.workspace.id),
                'workspace_name': instance.workspace.team_name,
                'user_id': instance.slack_user.slack_user_id if instance.slack_user else None,
                'text': instance.text,
                'timestamp': instance.message_ts,
                'thread_ts': instance.thread_ts,
                'is_thread_reply': instance.is_thread_reply,
                'is_dm': instance.channel.channel_type in ['im', 'mpim'],
                'created_at': instance.created_at.isoformat(),
                'event_type': 'database_message'
            }

            # Broadcast to WebSocket consumers
            groups = [
                f"slack_messages_anonymous",
                f"workspace_{instance.workspace.id}_anonymous",
            ]

            if not message_data['is_dm']:
                groups.append(f"channel_{instance.channel.channel_id}_anonymous")

            for group in groups:
                async_to_sync(channel_layer.group_send)(group, {
                    'type': 'slack_channel_message' if not message_data['is_dm'] else 'slack_dm',
                    'message': message_data
                })

            logger.info(f"Broadcasted database message {instance.id} to WebSocket consumers")

        except Exception as e:
            logger.error(f"Error broadcasting message signal: {str(e)}")


@receiver(post_save, sender=SlackChannel)
def handle_channel_updated(sender, instance, created, **kwargs):
    """
    Handle channel creation or updates
    """
    if channel_layer:
        try:
            channel_data = {
                'id': instance.channel_id,
                'name': instance.channel_name,
                'type': instance.channel_type,
                'is_private': instance.is_private,
                'is_archived': instance.is_archived,
                'workspace_id': str(instance.workspace.id),
                'event_type': 'channel_created' if created else 'channel_updated',
                'timestamp': instance.updated_at.isoformat()
            }

            # Broadcast channel updates to workspace notifications
            group = f"slack_notifications_anonymous"
            async_to_sync(channel_layer.group_send)(group, {
                'type': 'slack_notification',
                'notification': {
                    'type': 'channel_activity',
                    'data': channel_data
                }
            })

            logger.info(f"Broadcasted channel {'creation' if created else 'update'} for {instance.channel_id}")

        except Exception as e:
            logger.error(f"Error broadcasting channel signal: {str(e)}")


@receiver(post_save, sender=SlackWorkspace)
def handle_workspace_updated(sender, instance, created, **kwargs):
    """
    Handle workspace creation or updates
    """
    if channel_layer:
        try:
            workspace_data = {
                'id': str(instance.id),
                'team_id': instance.team_id,
                'team_name': instance.team_name,
                'team_domain': instance.team_domain,
                'is_active': instance.is_active,
                'event_type': 'workspace_created' if created else 'workspace_updated',
                'timestamp': instance.updated_at.isoformat()
            }

            # Broadcast workspace updates
            group = f"slack_notifications_anonymous"
            async_to_sync(channel_layer.group_send)(group, {
                'type': 'slack_notification',
                'notification': {
                    'type': 'workspace_activity',
                    'data': workspace_data
                }
            })

            logger.info(f"Broadcasted workspace {'creation' if created else 'update'} for {instance.team_name}")

        except Exception as e:
            logger.error(f"Error broadcasting workspace signal: {str(e)}")