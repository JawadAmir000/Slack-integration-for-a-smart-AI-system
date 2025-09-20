from rest_framework import serializers
from apps.core.models import SlackWorkspace, SlackUser, SlackChannel, SlackMessage, SlackAppConfiguration


class SlackAppConfigurationSerializer(serializers.ModelSerializer):
    """
    Serializer for SlackAppConfiguration model
    """
    # Hide sensitive fields from API responses
    client_secret = serializers.CharField(write_only=True)
    signing_secret = serializers.CharField(write_only=True)

    # Add computed fields
    is_configured = serializers.SerializerMethodField()
    last_verification_status = serializers.SerializerMethodField()

    class Meta:
        model = SlackAppConfiguration
        fields = (
            'id', 'client_identifier', 'app_name', 'client_id', 'client_secret',
            'signing_secret', 'redirect_uri', 'scopes', 'client_name', 'client_email',
            'is_active', 'is_verified', 'verification_errors', 'usage_count',
            'last_used_at', 'created_at', 'updated_at', 'is_configured',
            'last_verification_status'
        )
        read_only_fields = (
            'id', 'is_verified', 'verification_errors', 'usage_count',
            'last_used_at', 'created_at', 'updated_at'
        )

    def get_is_configured(self, obj):
        """Check if all required fields are configured"""
        return all([
            obj.client_id,
            obj.client_secret,
            obj.signing_secret,
            obj.redirect_uri
        ])

    def get_last_verification_status(self, obj):
        """Get verification status message"""
        if not obj.is_verified and obj.verification_errors:
            return f"Failed: {obj.verification_errors[:100]}..."
        elif obj.is_verified:
            return "Verified successfully"
        else:
            return "Not verified"

    def validate_client_identifier(self, value):
        """Validate client identifier format"""
        if not value.replace('-', '').replace('_', '').isalnum():
            raise serializers.ValidationError(
                "Client identifier must contain only letters, numbers, hyphens, and underscores."
            )
        return value.lower()  # Normalize to lowercase

    def validate_scopes(self, value):
        """Validate scopes format"""
        if not value:
            return value

        scopes_list = [s.strip() for s in value.split(',')]
        for scope in scopes_list:
            if not scope.replace(':', '').replace('_', '').replace('.', '').isalnum():
                raise serializers.ValidationError(f"Invalid scope format: {scope}")
        return value


class SlackAppConfigurationCreateSerializer(SlackAppConfigurationSerializer):
    """
    Serializer for creating SlackAppConfiguration (includes sensitive fields)
    """
    client_secret = serializers.CharField(required=True)
    signing_secret = serializers.CharField(required=True)


class SlackAppConfigurationPublicSerializer(serializers.ModelSerializer):
    """
    Public serializer for SlackAppConfiguration (no sensitive data)
    """
    is_configured = serializers.SerializerMethodField()

    class Meta:
        model = SlackAppConfiguration
        fields = (
            'id', 'client_identifier', 'app_name', 'client_name',
            'is_active', 'is_verified', 'usage_count', 'last_used_at',
            'created_at', 'is_configured'
        )

    def get_is_configured(self, obj):
        """Check if configuration is complete"""
        return all([obj.client_id, obj.client_secret, obj.signing_secret])


class SlackWorkspaceSerializer(serializers.ModelSerializer):
    """
    Serializer for SlackWorkspace model
    """
    class Meta:
        model = SlackWorkspace
        fields = ('id', 'team_id', 'team_name', 'team_domain', 'team_url', 'is_active', 'created_at')
        read_only_fields = ('id', 'created_at')


class SlackUserSerializer(serializers.ModelSerializer):
    """
    Serializer for SlackUser model
    """
    workspace = SlackWorkspaceSerializer(read_only=True)
    
    class Meta:
        model = SlackUser
        fields = (
            'id', 'slack_user_id', 'slack_username', 'slack_email', 
            'workspace', 'scopes', 'is_active', 'created_at'
        )
        read_only_fields = ('id', 'access_token', 'refresh_token', 'created_at')


class SlackChannelSerializer(serializers.ModelSerializer):
    """
    Serializer for SlackChannel model
    """
    workspace = SlackWorkspaceSerializer(read_only=True)
    
    class Meta:
        model = SlackChannel
        fields = (
            'id', 'channel_id', 'channel_name', 'channel_type', 
            'is_private', 'is_archived', 'workspace', 'created_at'
        )
        read_only_fields = ('id', 'created_at')


class SlackMessageSerializer(serializers.ModelSerializer):
    """
    Serializer for SlackMessage model
    """
    channel = SlackChannelSerializer(read_only=True)
    slack_user = SlackUserSerializer(read_only=True)
    
    class Meta:
        model = SlackMessage
        fields = (
            'id', 'message_ts', 'message_type', 'text', 'thread_ts', 
            'is_thread_reply', 'channel', 'slack_user', 'created_at'
        )
        read_only_fields = ('id', 'created_at')


class SendMessageSerializer(serializers.Serializer):
    """
    Serializer for sending messages to Slack
    """
    channel = serializers.CharField(max_length=50, help_text="Channel ID or name")
    text = serializers.CharField(help_text="Message text")
    thread_ts = serializers.CharField(max_length=50, required=False, help_text="Thread timestamp for replies")
    as_user = serializers.BooleanField(default=True, help_text="Send as authenticated user")


class UploadFileSerializer(serializers.Serializer):
    """
    Serializer for uploading files to Slack
    """
    channels = serializers.CharField(help_text="Comma-separated list of channel IDs")
    file = serializers.FileField(required=False, help_text="File to upload")
    content = serializers.CharField(required=False, help_text="Text content to upload as file")
    filename = serializers.CharField(max_length=255, required=False, help_text="Filename")
    title = serializers.CharField(max_length=255, required=False, help_text="File title")
    
    def validate(self, data):
        if not data.get('file') and not data.get('content'):
            raise serializers.ValidationError("Either file or content must be provided")
        return data


class CreateChannelSerializer(serializers.Serializer):
    """
    Serializer for creating Slack channels
    """
    name = serializers.CharField(max_length=80, help_text="Channel name (without #)")
    is_private = serializers.BooleanField(default=False, help_text="Create private channel")
    
    def validate_name(self, value):
        # Slack channel name validation
        if not value.islower():
            raise serializers.ValidationError("Channel name must be lowercase")
        if not value.replace('-', '').replace('_', '').isalnum():
            raise serializers.ValidationError("Channel name can only contain letters, numbers, hyphens, and underscores")
        if len(value) > 21:
            raise serializers.ValidationError("Channel name must be 21 characters or less")
        return value


class JoinChannelSerializer(serializers.Serializer):
    """
    Serializer for joining Slack channels
    """
    channel = serializers.CharField(max_length=50, help_text="Channel ID or name")


class AddReactionSerializer(serializers.Serializer):
    """
    Serializer for adding reactions to messages
    """
    channel = serializers.CharField(max_length=50, help_text="Channel ID")
    timestamp = serializers.CharField(max_length=50, help_text="Message timestamp")
    name = serializers.CharField(max_length=100, help_text="Emoji name (without colons)")


class SlackOAuthInitiateSerializer(serializers.Serializer):
    """
    Serializer for OAuth initiation
    """
    state = serializers.CharField(max_length=255, required=False, help_text="Optional state parameter")


class SlackOAuthCallbackSerializer(serializers.Serializer):
    """
    Serializer for OAuth callback
    """
    code = serializers.CharField(required=False, help_text="OAuth authorization code")
    error = serializers.CharField(required=False, help_text="OAuth error code")
    error_description = serializers.CharField(required=False, help_text="OAuth error description")
    state = serializers.CharField(max_length=255, required=False, help_text="Optional state parameter")

    def validate(self, data):
        """Validate that either code or error is present"""
        if not data.get('code') and not data.get('error'):
            raise serializers.ValidationError("Either 'code' or 'error' parameter must be present")
        return data


class ReadMessagesSerializer(serializers.Serializer):
    """
    Serializer for reading messages from Slack channels
    """
    channel = serializers.CharField(max_length=50, required=False, help_text="Channel ID or name (required for single channel)")
    limit = serializers.IntegerField(default=50, min_value=1, max_value=1000, help_text="Number of messages to retrieve (1-1000)")
    oldest = serializers.CharField(max_length=50, required=False, help_text="Start of time range (timestamp)")
    latest = serializers.CharField(max_length=50, required=False, help_text="End of time range (timestamp)")
    cursor = serializers.CharField(max_length=255, required=False, help_text="Pagination cursor")
    include_all_metadata = serializers.BooleanField(default=False, help_text="Include additional message metadata")

    def validate(self, data):
        """Custom validation for message reading"""
        # If this is for a single channel read operation, channel is required
        view = self.context.get('view')
        if view and hasattr(view, 'action') and view.action != 'read_all':
            if not data.get('channel'):
                raise serializers.ValidationError("Channel is required for single channel operations")
        return data


class ReadAllChannelsMessagesSerializer(serializers.Serializer):
    """
    Serializer for reading messages from all accessible channels
    """
    limit_per_channel = serializers.IntegerField(default=20, min_value=1, max_value=100, help_text="Number of messages per channel (1-100)")
    oldest = serializers.CharField(max_length=50, required=False, help_text="Start of time range (timestamp)")
    latest = serializers.CharField(max_length=50, required=False, help_text="End of time range (timestamp)")
    channel_types = serializers.CharField(
        default="public_channel,private_channel",
        help_text="Channel types to include (comma-separated: public_channel, private_channel, mpim, im)"
    )
    include_archived = serializers.BooleanField(default=False, help_text="Include archived channels")

    def validate_channel_types(self, value):
        """Validate channel types"""
        valid_types = ['public_channel', 'private_channel', 'mpim', 'im']
        requested_types = [t.strip() for t in value.split(',')]

        for channel_type in requested_types:
            if channel_type not in valid_types:
                raise serializers.ValidationError(f"Invalid channel type: {channel_type}. Valid types: {', '.join(valid_types)}")

        return value


class SlackMessageSerializer(serializers.Serializer):
    """
    Serializer for individual Slack message data
    """
    type = serializers.CharField(read_only=True)
    subtype = serializers.CharField(read_only=True, required=False)
    text = serializers.CharField(read_only=True)
    user = serializers.CharField(read_only=True, required=False)
    username = serializers.CharField(read_only=True, required=False)
    bot_id = serializers.CharField(read_only=True, required=False)
    ts = serializers.CharField(read_only=True)  # timestamp
    thread_ts = serializers.CharField(read_only=True, required=False)
    reply_count = serializers.IntegerField(read_only=True, required=False)
    edited = serializers.DictField(read_only=True, required=False)
    reactions = serializers.ListField(read_only=True, required=False)
    attachments = serializers.ListField(read_only=True, required=False)
    blocks = serializers.ListField(read_only=True, required=False)
    files = serializers.ListField(read_only=True, required=False)


class ChannelMessagesResponseSerializer(serializers.Serializer):
    """
    Serializer for channel messages response
    """
    channel = serializers.CharField(read_only=True)
    messages = SlackMessageSerializer(many=True, read_only=True)
    has_more = serializers.BooleanField(read_only=True)
    response_metadata = serializers.DictField(read_only=True, required=False)
    ok = serializers.BooleanField(read_only=True)


class MultiChannelMessagesResponseSerializer(serializers.Serializer):
    """
    Serializer for multiple channels messages response
    """
    channels = serializers.DictField(read_only=True)
    channels_metadata = serializers.DictField(read_only=True, required=False)
    successful_channels = serializers.ListField(read_only=True)
    failed_channels = serializers.ListField(read_only=True)
    total_messages = serializers.IntegerField(read_only=True)
    summary = serializers.DictField(read_only=True, required=False)


# Direct Message Serializers

class SendDMSerializer(serializers.Serializer):
    """
    Serializer for sending direct messages
    """
    user_id = serializers.CharField(max_length=50, help_text="Slack user ID to send DM to")
    text = serializers.CharField(help_text="Message text")
    thread_ts = serializers.CharField(max_length=50, required=False, help_text="Thread timestamp for replies")
    as_user = serializers.BooleanField(default=True, help_text="Send as authenticated user")


class DMUserSerializer(serializers.Serializer):
    """
    Serializer for workspace users (for DM recipient selection)
    """
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    real_name = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True, required=False)
    email = serializers.EmailField(read_only=True, required=False)
    image = serializers.URLField(read_only=True, required=False)
    is_admin = serializers.BooleanField(read_only=True)
    is_owner = serializers.BooleanField(read_only=True)


class DMConversationSerializer(serializers.Serializer):
    """
    Serializer for DM conversation info
    """
    id = serializers.CharField(read_only=True)
    is_im = serializers.BooleanField(read_only=True)
    is_mpim = serializers.BooleanField(read_only=True)
    user = serializers.CharField(read_only=True, required=False)
    created = serializers.IntegerField(read_only=True)
    is_user_deleted = serializers.BooleanField(read_only=True)


class ReadDMSerializer(serializers.Serializer):
    """
    Serializer for reading direct messages
    """
    dm_channel = serializers.CharField(max_length=50, required=False, help_text="DM channel ID (optional for single DM)")
    user_id = serializers.CharField(max_length=50, required=False, help_text="User ID for DM (alternative to dm_channel)")
    limit = serializers.IntegerField(default=50, min_value=1, max_value=1000, help_text="Number of messages to retrieve")
    oldest = serializers.CharField(max_length=50, required=False, help_text="Start of time range (timestamp)")
    latest = serializers.CharField(max_length=50, required=False, help_text="End of time range (timestamp)")
    cursor = serializers.CharField(max_length=255, required=False, help_text="Pagination cursor")

    def validate(self, data):
        """Validate that either dm_channel or user_id is provided"""
        if not data.get('dm_channel') and not data.get('user_id'):
            raise serializers.ValidationError("Either 'dm_channel' or 'user_id' must be provided")
        return data


class ReadAllDMsSerializer(serializers.Serializer):
    """
    Serializer for reading messages from all DM conversations
    """
    limit_per_dm = serializers.IntegerField(default=20, min_value=1, max_value=100, help_text="Number of messages per DM (1-100)")
    oldest = serializers.CharField(max_length=50, required=False, help_text="Start of time range (timestamp)")
    latest = serializers.CharField(max_length=50, required=False, help_text="End of time range (timestamp)")
    include_mpim = serializers.BooleanField(default=True, help_text="Include multi-person direct messages")


class DMMessageSerializer(serializers.Serializer):
    """
    Serializer for individual DM message data
    """
    type = serializers.CharField(read_only=True)
    subtype = serializers.CharField(read_only=True, required=False)
    text = serializers.CharField(read_only=True)
    user = serializers.CharField(read_only=True, required=False)
    username = serializers.CharField(read_only=True, required=False)
    bot_id = serializers.CharField(read_only=True, required=False)
    ts = serializers.CharField(read_only=True)  # timestamp
    thread_ts = serializers.CharField(read_only=True, required=False)
    reply_count = serializers.IntegerField(read_only=True, required=False)
    edited = serializers.DictField(read_only=True, required=False)
    reactions = serializers.ListField(read_only=True, required=False)
    attachments = serializers.ListField(read_only=True, required=False)
    blocks = serializers.ListField(read_only=True, required=False)
    files = serializers.ListField(read_only=True, required=False)


class DMMessagesResponseSerializer(serializers.Serializer):
    """
    Serializer for DM messages response
    """
    dm_channel = serializers.CharField(read_only=True)
    messages = DMMessageSerializer(many=True, read_only=True)
    has_more = serializers.BooleanField(read_only=True)
    response_metadata = serializers.DictField(read_only=True, required=False)
    conversation_info = serializers.DictField(read_only=True, required=False)
    ok = serializers.BooleanField(read_only=True)


class MultiDMMessagesResponseSerializer(serializers.Serializer):
    """
    Serializer for multiple DM conversations messages response
    """
    conversations = serializers.DictField(read_only=True)
    successful_conversations = serializers.ListField(read_only=True)
    failed_conversations = serializers.ListField(read_only=True)
    total_messages = serializers.IntegerField(read_only=True)
    summary = serializers.DictField(read_only=True, required=False)