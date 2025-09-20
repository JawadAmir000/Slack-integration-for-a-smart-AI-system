from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from cryptography.fernet import Fernet
from django.conf import settings
import base64
import os


class TimeStampedModel(models.Model):
    """
    Abstract base class model that provides self-updating
    ``created_at`` and ``updated_at`` fields.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class EncryptedTextField(models.TextField):
    """
    Custom field that encrypts data before storing and decrypts when retrieving
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_encryption_key(self):
        """Get or create encryption key"""
        encryption_key = getattr(settings, 'SLACK_ENCRYPTION_KEY', None)
        if not encryption_key:
            # Use Django SECRET_KEY as base for encryption key
            from cryptography.fernet import Fernet
            import base64
            import hashlib

            # Create a 32-byte key from Django SECRET_KEY
            key_material = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
            encryption_key = base64.urlsafe_b64encode(key_material)
        elif isinstance(encryption_key, str):
            encryption_key = encryption_key.encode()
        return encryption_key

    def encrypt_value(self, value):
        if not value:
            return value
        fernet = Fernet(self.get_encryption_key())
        encrypted_value = fernet.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted_value).decode()

    def decrypt_value(self, value):
        if not value:
            return value
        try:
            fernet = Fernet(self.get_encryption_key())
            encrypted_data = base64.urlsafe_b64decode(value.encode())
            decrypted_value = fernet.decrypt(encrypted_data)
            result = decrypted_value.decode()
            return result
        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to decrypt value: {str(e)}")
            return value  # Return as-is if decryption fails (backward compatibility)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self.decrypt_value(value)

    def to_python(self, value):
        if isinstance(value, str):
            return value
        return value

    def get_prep_value(self, value):
        return self.encrypt_value(value)


class SlackAppConfiguration(TimeStampedModel):
    """
    Model to store client-specific Slack app configurations for multi-tenancy
    """
    client_identifier = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique identifier for the client (used in URLs and API calls)"
    )
    app_name = models.CharField(
        max_length=255,
        help_text="Display name for the Slack app"
    )

    # Encrypted Slack app credentials
    client_id = EncryptedTextField(help_text="Slack app client ID")
    client_secret = EncryptedTextField(help_text="Slack app client secret")
    signing_secret = EncryptedTextField(help_text="Slack app signing secret")

    # App configuration
    redirect_uri = models.URLField(
        help_text="OAuth redirect URI for this client"
    )
    scopes = models.TextField(
        default='channels:read,groups:read,im:read,mpim:read,chat:write,files:write,users:read,im:write,mpim:write,users:read.email',
        help_text="Comma-separated list of OAuth scopes"
    )

    # Client metadata
    client_name = models.CharField(
        max_length=255,
        help_text="Human-readable client name"
    )
    client_email = models.EmailField(
        null=True, blank=True,
        help_text="Contact email for the client"
    )

    # Status and configuration
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this configuration is active"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether the configuration has been verified to work"
    )
    verification_errors = models.TextField(
        null=True, blank=True,
        help_text="Last verification error messages"
    )

    # Usage tracking
    last_used_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When this configuration was last used"
    )
    usage_count = models.IntegerField(
        default=0,
        help_text="Number of times this configuration has been used"
    )

    class Meta:
        db_table = 'slack_app_configurations'
        verbose_name = 'Slack App Configuration'
        verbose_name_plural = 'Slack App Configurations'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.app_name} ({self.client_identifier})"

    def clean(self):
        """Validate the configuration"""
        super().clean()

        # Validate client_identifier format (alphanumeric and hyphens only)
        if not self.client_identifier.replace('-', '').replace('_', '').isalnum():
            raise ValidationError({
                'client_identifier': 'Client identifier must contain only letters, numbers, hyphens, and underscores.'
            })

        # Validate scopes format
        if self.scopes:
            scopes_list = [s.strip() for s in self.scopes.split(',')]
            invalid_scopes = [s for s in scopes_list if not s.replace(':', '').replace('_', '').replace('.', '').isalnum()]
            if invalid_scopes:
                raise ValidationError({
                    'scopes': f'Invalid scopes format: {", ".join(invalid_scopes)}'
                })

    def get_scopes_list(self):
        """Return scopes as a list"""
        return [s.strip() for s in self.scopes.split(',') if s.strip()]

    def increment_usage(self):
        """Increment usage counter and update last used timestamp"""
        from django.utils import timezone
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])

    def mark_verified(self, is_verified=True, error_message=None):
        """Mark configuration as verified or failed"""
        self.is_verified = is_verified
        self.verification_errors = error_message
        self.save(update_fields=['is_verified', 'verification_errors'])


class SlackWorkspace(TimeStampedModel):
    """
    Model to store Slack workspace information
    """
    app_config = models.ForeignKey(
        SlackAppConfiguration,
        on_delete=models.CASCADE,
        null=True, blank=True,
        help_text="Associated Slack app configuration (for multi-tenant support)"
    )
    team_id = models.CharField(max_length=50, unique=True, help_text="Slack team ID")
    team_name = models.CharField(max_length=255, help_text="Slack team/workspace name")
    team_domain = models.CharField(max_length=255, null=True, blank=True, help_text="Slack team domain")
    team_url = models.URLField(null=True, blank=True, help_text="Slack workspace URL")
    is_active = models.BooleanField(default=True, help_text="Whether this workspace is active")

    class Meta:
        db_table = 'slack_workspaces'
        verbose_name = 'Slack Workspace'
        verbose_name_plural = 'Slack Workspaces'

    def __str__(self):
        return f"{self.team_name} ({self.team_id})"


class SlackUser(TimeStampedModel):
    """
    Model to store Slack user information and tokens
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, help_text="Django user")
    workspace = models.ForeignKey(SlackWorkspace, on_delete=models.CASCADE, help_text="Slack workspace")
    slack_user_id = models.CharField(max_length=50, help_text="Slack user ID")
    slack_username = models.CharField(max_length=255, null=True, blank=True, help_text="Slack username")
    slack_email = models.EmailField(null=True, blank=True, help_text="Slack user email")
    
    # OAuth tokens
    access_token = models.TextField(help_text="Slack OAuth access token")
    refresh_token = models.TextField(null=True, blank=True, help_text="Slack OAuth refresh token")
    token_expires_at = models.DateTimeField(null=True, blank=True, help_text="Token expiration time")
    scopes = models.TextField(help_text="Granted OAuth scopes")
    
    is_active = models.BooleanField(default=True, help_text="Whether this user connection is active")

    class Meta:
        db_table = 'slack_users'
        verbose_name = 'Slack User'
        verbose_name_plural = 'Slack Users'
        unique_together = ['workspace', 'slack_user_id']

    def __str__(self):
        return f"{self.slack_username or self.slack_user_id} in {self.workspace.team_name}"


class SlackBot(TimeStampedModel):
    """
    Model to store Slack bot information and tokens
    """
    workspace = models.OneToOneField(SlackWorkspace, on_delete=models.CASCADE, help_text="Slack workspace")
    bot_user_id = models.CharField(max_length=50, help_text="Bot user ID")
    bot_access_token = models.TextField(help_text="Bot access token")
    bot_scopes = models.TextField(help_text="Bot OAuth scopes")
    app_id = models.CharField(max_length=50, null=True, blank=True, help_text="Slack app ID")
    
    is_active = models.BooleanField(default=True, help_text="Whether this bot is active")

    class Meta:
        db_table = 'slack_bots'
        verbose_name = 'Slack Bot'
        verbose_name_plural = 'Slack Bots'

    def __str__(self):
        return f"Bot {self.bot_user_id} in {self.workspace.team_name}"


class SlackChannel(TimeStampedModel):
    """
    Model to store Slack channel information
    """
    CHANNEL_TYPES = (
        ('public_channel', 'Public Channel'),
        ('private_channel', 'Private Channel'),
        ('im', 'Direct Message'),
        ('mpim', 'Multi-person Direct Message'),
    )
    
    workspace = models.ForeignKey(SlackWorkspace, on_delete=models.CASCADE, help_text="Slack workspace")
    channel_id = models.CharField(max_length=50, help_text="Slack channel ID")
    channel_name = models.CharField(max_length=255, null=True, blank=True, help_text="Channel name")
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPES, help_text="Type of channel")
    is_private = models.BooleanField(default=False, help_text="Whether channel is private")
    is_archived = models.BooleanField(default=False, help_text="Whether channel is archived")
    
    class Meta:
        db_table = 'slack_channels'
        verbose_name = 'Slack Channel'
        verbose_name_plural = 'Slack Channels'
        unique_together = ['workspace', 'channel_id']

    def __str__(self):
        return f"#{self.channel_name or self.channel_id} in {self.workspace.team_name}"


class SlackMessage(TimeStampedModel):
    """
    Model to store Slack message information
    """
    MESSAGE_TYPES = (
        ('message', 'Message'),
        ('file_share', 'File Share'),
        ('channel_join', 'Channel Join'),
        ('channel_leave', 'Channel Leave'),
    )
    
    workspace = models.ForeignKey(SlackWorkspace, on_delete=models.CASCADE, help_text="Slack workspace")
    channel = models.ForeignKey(SlackChannel, on_delete=models.CASCADE, help_text="Slack channel")
    slack_user = models.ForeignKey(SlackUser, on_delete=models.CASCADE, null=True, blank=True, help_text="Message sender")
    
    message_ts = models.CharField(max_length=50, help_text="Slack message timestamp")
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='message', help_text="Type of message")
    text = models.TextField(null=True, blank=True, help_text="Message text")
    
    # Thread information
    thread_ts = models.CharField(max_length=50, null=True, blank=True, help_text="Thread timestamp")
    is_thread_reply = models.BooleanField(default=False, help_text="Whether this is a thread reply")
    
    class Meta:
        db_table = 'slack_messages'
        verbose_name = 'Slack Message'
        verbose_name_plural = 'Slack Messages'
        unique_together = ['workspace', 'channel', 'message_ts']

    def __str__(self):
        return f"Message {self.message_ts} in {self.channel}"