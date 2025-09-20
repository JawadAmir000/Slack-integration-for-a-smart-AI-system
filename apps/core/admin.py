from django.contrib import admin
from .models import SlackWorkspace, SlackUser, SlackBot, SlackChannel, SlackMessage


@admin.register(SlackWorkspace)
class SlackWorkspaceAdmin(admin.ModelAdmin):
    list_display = ('team_name', 'team_id', 'team_domain', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('team_name', 'team_id', 'team_domain')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SlackUser)
class SlackUserAdmin(admin.ModelAdmin):
    list_display = ('slack_username', 'slack_user_id', 'workspace', 'user', 'is_active', 'created_at')
    list_filter = ('is_active', 'workspace', 'created_at')
    search_fields = ('slack_username', 'slack_user_id', 'slack_email')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user', 'workspace')


@admin.register(SlackBot)
class SlackBotAdmin(admin.ModelAdmin):
    list_display = ('bot_user_id', 'workspace', 'app_id', 'is_active', 'created_at')
    list_filter = ('is_active', 'workspace', 'created_at')
    search_fields = ('bot_user_id', 'app_id')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('workspace',)


@admin.register(SlackChannel)
class SlackChannelAdmin(admin.ModelAdmin):
    list_display = ('channel_name', 'channel_id', 'workspace', 'channel_type', 'is_private', 'is_archived')
    list_filter = ('channel_type', 'is_private', 'is_archived', 'workspace', 'created_at')
    search_fields = ('channel_name', 'channel_id')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('workspace',)


@admin.register(SlackMessage)
class SlackMessageAdmin(admin.ModelAdmin):
    list_display = ('message_ts', 'channel', 'slack_user', 'message_type', 'is_thread_reply', 'created_at')
    list_filter = ('message_type', 'is_thread_reply', 'channel__workspace', 'created_at')
    search_fields = ('text', 'message_ts')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('workspace', 'channel', 'slack_user')