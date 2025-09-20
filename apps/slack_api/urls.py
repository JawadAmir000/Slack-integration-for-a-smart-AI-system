from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

app_name = 'slack_api'

urlpatterns = [
    # API overview endpoint
    path('', views.SlackAPIOverviewView.as_view(), name='api_overview'),

    # Configuration management endpoints (admin only)
    path('config/', views.SlackConfigListCreateView.as_view(), name='config_list_create'),
    path('config/<str:client_identifier>/', views.SlackConfigDetailView.as_view(), name='config_detail'),
    path('config/<str:client_identifier>/verify/', views.SlackConfigVerifyView.as_view(), name='config_verify'),

    # Generic OAuth endpoint - automatically redirects to Slack
    path('oauth/connect/', views.GenericSlackOAuthView.as_view(), name='oauth_generic'),

    # Automatic configuration endpoint
    path('auth/auto/', views.SlackAutoOAuthInitiateView.as_view(), name='oauth_auto_initiate'),

    # Legacy endpoints (backward compatibility - no client identifier)
    path('auth/initiate/', views.SlackOAuthInitiateView.as_view(), name='oauth_initiate_legacy'),
    path('auth/callback', views.SlackOAuthCallbackView.as_view(), name='oauth_callback_legacy_no_slash'),
    path('auth/callback/', views.SlackOAuthCallbackView.as_view(), name='oauth_callback_legacy'),
    path('workspaces/', views.SlackWorkspacesView.as_view(), name='workspaces_legacy'),
    path('channels/', views.SlackChannelsView.as_view(), name='channels_legacy'),
    path('channels/bulk-join/', views.SlackBulkJoinChannelsView.as_view(), name='bulk_join_channels_legacy'),
    path('messages/send/', views.SlackMessagesView.as_view(), name='send_message_legacy'),
    path('messages/read/', views.SlackMessagesReadView.as_view(), name='read_messages_legacy'),
    path('messages/read/all/', views.SlackMessagesReadView.as_view(), name='read_all_messages_legacy'),
    path('user/info/', views.slack_user_info, name='user_info_legacy'),

    # Client-specific endpoints (multi-tenant)
    path('<str:client_identifier>/auth/initiate/', views.SlackOAuthInitiateView.as_view(), name='oauth_initiate'),
    path('<str:client_identifier>/auth/callback/', views.SlackOAuthCallbackView.as_view(), name='oauth_callback'),

    # Workspace endpoints
    path('<str:client_identifier>/workspaces/', views.SlackWorkspacesView.as_view(), name='workspaces'),

    # Channel endpoints
    path('<str:client_identifier>/channels/', views.SlackChannelsView.as_view(), name='channels'),
    path('<str:client_identifier>/channels/<int:workspace_id>/', views.SlackChannelsView.as_view(), name='workspace_channels'),
    path('<str:client_identifier>/channels/join/', views.SlackChannelJoinView.as_view(), name='join_channel'),
    path('<str:client_identifier>/channels/bulk-join/', views.SlackBulkJoinChannelsView.as_view(), name='bulk_join_channels'),

    # Message endpoints
    path('<str:client_identifier>/messages/send/', views.SlackMessagesView.as_view(), name='send_message'),
    path('<str:client_identifier>/messages/read/', views.SlackMessagesReadView.as_view(), name='read_messages'),
    path('<str:client_identifier>/messages/read/all/', views.SlackMessagesReadView.as_view(), name='read_all_messages'),
    path('<str:client_identifier>/messages/reaction/', views.SlackReactionView.as_view(), name='add_reaction'),

    # File endpoints
    path('<str:client_identifier>/files/upload/', views.SlackFilesView.as_view(), name='upload_file'),

    # User endpoints
    path('<str:client_identifier>/user/info/', views.slack_user_info, name='user_info'),

    # Direct Message endpoints
    path('<str:client_identifier>/dm/send/', csrf_exempt(views.SlackDMView.as_view()), name='send_dm'),
    path('<str:client_identifier>/dm/read/', csrf_exempt(views.SlackDMReadView.as_view()), name='read_dm'),
    path('<str:client_identifier>/dm/read/all/', csrf_exempt(views.SlackDMReadView.as_view()), name='read_all_dms'),
    path('<str:client_identifier>/dm/users/', csrf_exempt(views.SlackDMUsersView.as_view()), name='dm_users'),
    path('<str:client_identifier>/dm/conversations/', csrf_exempt(views.SlackDMConversationsView.as_view()), name='dm_conversations'),

    # Legacy DM endpoints (backward compatibility)
    path('dm/send/', csrf_exempt(views.SlackDMView.as_view()), name='send_dm_legacy'),
    path('dm/read/', csrf_exempt(views.SlackDMReadView.as_view()), name='read_dm_legacy'),
    path('dm/read/all/', csrf_exempt(views.SlackDMReadView.as_view()), name='read_all_dms_legacy'),
    path('dm/users/', csrf_exempt(views.SlackDMUsersView.as_view()), name='dm_users_legacy'),
    path('dm/conversations/', csrf_exempt(views.SlackDMConversationsView.as_view()), name='dm_conversations_legacy'),
]