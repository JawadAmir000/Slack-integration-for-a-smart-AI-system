import logging
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.models import User
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .services import SlackOAuthService, SlackAPIService, SlackDataService
from .serializers import (
    SlackOAuthInitiateSerializer, SlackOAuthCallbackSerializer,
    SlackWorkspaceSerializer, SlackUserSerializer, SlackChannelSerializer,
    SendMessageSerializer, UploadFileSerializer, CreateChannelSerializer,
    JoinChannelSerializer, AddReactionSerializer,
    SlackAppConfigurationSerializer, SlackAppConfigurationCreateSerializer,
    SlackAppConfigurationPublicSerializer, ReadMessagesSerializer,
    ReadAllChannelsMessagesSerializer, ChannelMessagesResponseSerializer,
    MultiChannelMessagesResponseSerializer, SendDMSerializer, DMUserSerializer,
    ReadDMSerializer, ReadAllDMsSerializer, DMMessagesResponseSerializer,
    MultiDMMessagesResponseSerializer
)
from apps.core.models import SlackUser, SlackWorkspace, SlackChannel, SlackBot, SlackAppConfiguration

logger = logging.getLogger('slack_api')


# API Overview View

class SlackAPIOverviewView(APIView):
    """
    Slack API Overview - provides information about available endpoints
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """Get API overview"""
        return Response({
            'message': 'Slack Integration API',
            'version': '1.0',
            'features': [
                'Multi-tenant Slack app configurations',
                'OAuth 2.0 authentication flow',
                'Workspace and channel management',
                'Message sending and reading',
                'Read messages from specific channels or all accessible channels',
                'File uploads and emoji reactions',
                'Legacy API compatibility'
            ],
            'endpoints': {
                'configuration': {
                    'list_configs': '/api/slack/config/',
                    'get_config': '/api/slack/config/{client_identifier}/',
                    'verify_config': '/api/slack/config/{client_identifier}/verify/'
                },
                'legacy': {
                    'oauth_initiate': '/api/slack/auth/initiate/',
                    'oauth_callback': '/api/slack/auth/callback/',
                    'workspaces': '/api/slack/workspaces/',
                    'channels': '/api/slack/channels/',
                    'send_message': '/api/slack/messages/send/',
                    'read_messages': '/api/slack/messages/read/?channel={channel_id}&limit=50',
                    'read_all_messages': '/api/slack/messages/read/all/?limit_per_channel=20',
                    'send_dm': '/api/slack/dm/send/',
                    'read_dm': '/api/slack/dm/read/?user_id={user_id}&limit=50',
                    'read_all_dms': '/api/slack/dm/read/all/?limit_per_dm=20',
                    'dm_users': '/api/slack/dm/users/',
                    'dm_conversations': '/api/slack/dm/conversations/',
                    'user_info': '/api/slack/user/info/'
                },
                'multi_tenant': {
                    'oauth_initiate': '/api/slack/{client_identifier}/auth/initiate/',
                    'oauth_callback': '/api/slack/{client_identifier}/auth/callback/',
                    'workspaces': '/api/slack/{client_identifier}/workspaces/',
                    'channels': '/api/slack/{client_identifier}/channels/',
                    'workspace_channels': '/api/slack/{client_identifier}/channels/{workspace_id}/',
                    'join_channel': '/api/slack/{client_identifier}/channels/join/',
                    'send_message': '/api/slack/{client_identifier}/messages/send/',
                    'read_messages': '/api/slack/{client_identifier}/messages/read/?channel={channel_id}&limit=50',
                    'read_all_messages': '/api/slack/{client_identifier}/messages/read/all/?limit_per_channel=20',
                    'send_dm': '/api/slack/{client_identifier}/dm/send/',
                    'read_dm': '/api/slack/{client_identifier}/dm/read/?user_id={user_id}&limit=50',
                    'read_all_dms': '/api/slack/{client_identifier}/dm/read/all/?limit_per_dm=20',
                    'dm_users': '/api/slack/{client_identifier}/dm/users/',
                    'dm_conversations': '/api/slack/{client_identifier}/dm/conversations/',
                    'add_reaction': '/api/slack/{client_identifier}/messages/reaction/',
                    'upload_file': '/api/slack/{client_identifier}/files/upload/',
                    'user_info': '/api/slack/{client_identifier}/user/info/'
                }
            },
            'authentication': 'Most endpoints require authentication. Configuration endpoints require admin privileges.',
            'documentation': 'Visit /config/ for web interface or /admin/ for Django admin panel'
        }, status=status.HTTP_200_OK)


# Configuration Management Views

class SlackConfigListCreateView(APIView):
    """
    List all Slack app configurations or create a new one
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        """List all configurations"""
        configs = SlackAppConfiguration.objects.all()
        serializer = SlackAppConfigurationPublicSerializer(configs, many=True)

        return Response({
            'configurations': serializer.data,
            'count': configs.count()
        }, status=status.HTTP_200_OK)

    def post(self, request, client_identifier=None):
        """Create new configuration"""
        serializer = SlackAppConfigurationCreateSerializer(data=request.data)
        if serializer.is_valid():
            config = serializer.save()
            response_serializer = SlackAppConfigurationPublicSerializer(config)

            logger.info(f"Created new Slack app configuration: {config.client_identifier}")

            return Response({
                'message': 'Configuration created successfully',
                'configuration': response_serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SlackConfigDetailView(APIView):
    """
    Retrieve, update or delete a specific Slack app configuration
    """
    permission_classes = [permissions.IsAdminUser]

    def get_object(self, client_identifier):
        return get_object_or_404(SlackAppConfiguration, client_identifier=client_identifier)

    def get(self, request, client_identifier):
        """Get configuration details"""
        config = self.get_object(client_identifier)
        serializer = SlackAppConfigurationSerializer(config)

        return Response({
            'configuration': serializer.data
        }, status=status.HTTP_200_OK)

    def put(self, request, client_identifier):
        """Update configuration"""
        config = self.get_object(client_identifier)
        serializer = SlackAppConfigurationSerializer(config, data=request.data, partial=True)

        if serializer.is_valid():
            config = serializer.save()

            # Reset verification status when configuration changes
            if any(field in request.data for field in ['client_id', 'client_secret', 'signing_secret']):
                config.mark_verified(False, "Configuration updated - verification required")

            logger.info(f"Updated Slack app configuration: {config.client_identifier}")

            return Response({
                'message': 'Configuration updated successfully',
                'configuration': SlackAppConfigurationPublicSerializer(config).data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, client_identifier):
        """Delete configuration and ALL related data"""
        from django.db import transaction
        from apps.core.models import SlackWorkspace, SlackChannel, SlackUser, SlackBot, SlackMessage

        config = self.get_object(client_identifier)
        client_id = config.client_identifier

        # Count records for logging
        workspaces_count = SlackWorkspace.objects.filter(app_config=config).count()
        channels_count = SlackChannel.objects.filter(workspace__app_config=config).count()
        users_count = SlackUser.objects.filter(workspace__app_config=config).count()
        bots_count = SlackBot.objects.filter(workspace__app_config=config).count()
        messages_count = SlackMessage.objects.filter(workspace__app_config=config).count()

        # Perform atomic deletion of all related data
        try:
            with transaction.atomic():
                # Delete all workspaces associated with this config
                # This will cascade delete channels, users, bots, messages due to FK relationships
                deleted_workspaces = SlackWorkspace.objects.filter(app_config=config)
                for workspace in deleted_workspaces:
                    workspace.delete()  # Cascade delete will handle related records

                # Delete the configuration itself
                config.delete()

                logger.info(
                    f"Deleted Slack app configuration '{client_id}' and all related data: "
                    f"{workspaces_count} workspaces, {channels_count} channels, "
                    f"{users_count} users, {bots_count} bots, {messages_count} messages"
                )

        except Exception as e:
            logger.error(f"Error deleting configuration '{client_id}': {str(e)}")
            return Response({
                'error': 'Failed to delete configuration',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'message': f'Configuration {client_id} and all related data deleted successfully',
            'deleted_records': {
                'workspaces': workspaces_count,
                'channels': channels_count,
                'users': users_count,
                'bots': bots_count,
                'messages': messages_count
            }
        }, status=status.HTTP_204_NO_CONTENT)


class SlackConfigVerifyView(APIView):
    """
    Verify a Slack app configuration by testing the connection
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, client_identifier):
        """Verify configuration"""
        try:
            config = get_object_or_404(SlackAppConfiguration, client_identifier=client_identifier)

            # Verify required fields are present
            if not all([config.client_id, config.client_secret, config.signing_secret]):
                config.mark_verified(False, "Missing required configuration fields")
                return Response({
                    'verified': False,
                    'error': 'Missing required configuration fields'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Test OAuth URL generation
            try:
                auth_url = SlackOAuthService.get_authorization_url_for_config(config)
                if not auth_url:
                    raise Exception("Failed to generate OAuth URL")
            except Exception as e:
                error_msg = f"OAuth URL generation failed: {str(e)}"
                config.mark_verified(False, error_msg)
                return Response({
                    'verified': False,
                    'error': error_msg
                }, status=status.HTTP_400_BAD_REQUEST)

            # Mark as verified if all tests pass
            config.mark_verified(True)

            logger.info(f"Verified Slack app configuration: {config.client_identifier}")

            return Response({
                'verified': True,
                'message': 'Configuration verified successfully',
                'auth_url': auth_url
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Configuration verification error: {str(e)}")
            return Response({
                'verified': False,
                'error': f'Verification failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# OAuth and API Views

class SlackOAuthInitiateView(APIView):
    """
    Initiate Slack OAuth 2.0 flow (supports multi-tenant)
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, client_identifier=None):
        """
        Get Slack OAuth authorization URL
        """
        serializer = SlackOAuthInitiateSerializer(data=request.GET)
        if serializer.is_valid():
            state = serializer.validated_data.get('state')

            # Generate auth URL with client-specific configuration
            auth_url = SlackOAuthService.get_authorization_url(
                state=state,
                client_identifier=client_identifier
            )

            response_data = {
                'auth_url': auth_url,
                'message': 'Redirect user to this URL to start OAuth flow'
            }

            # Add client info if available
            if client_identifier:
                response_data['client_identifier'] = client_identifier
                config = SlackOAuthService.get_app_config(client_identifier)
                if config:
                    response_data['client_name'] = config.client_name
                    response_data['app_name'] = config.app_name

            return Response(response_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SlackAutoOAuthInitiateView(APIView):
    """
    Automatically initiate Slack OAuth 2.0 flow using primary configuration
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Get Slack OAuth authorization URL using the primary active configuration
        """
        serializer = SlackOAuthInitiateSerializer(data=request.GET)
        if serializer.is_valid():
            state = serializer.validated_data.get('state')

            # Get auth URL and client identifier automatically
            auth_url, client_identifier = SlackOAuthService.get_auto_authorization_url(state=state)

            response_data = {
                'auth_url': auth_url,
                'client_identifier': client_identifier,
                'message': 'OAuth flow initiated automatically'
            }

            if client_identifier:
                response_data['client_name'] = SlackOAuthService.get_app_config(client_identifier).client_name if SlackOAuthService.get_app_config(client_identifier) else 'Unknown'

            logger.info(f"Auto OAuth initiated for client: {client_identifier}")
            return Response(response_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SlackOAuthCallbackView(APIView):
    """
    Handle Slack OAuth 2.0 callback (supports multi-tenant)
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, client_identifier=None):
        """
        Handle OAuth callback with authorization code or error
        """
        serializer = SlackOAuthCallbackSerializer(data=request.GET)
        if serializer.is_valid():
            # Check if this is an error response from Slack
            error = serializer.validated_data.get('error')
            if error:
                error_description = serializer.validated_data.get('error_description', 'No description provided')
                logger.error(f"OAuth error from Slack: {error} - {error_description}")

                # Redirect to error page with details
                error_url = f'/?error={error}&error_description={error_description}'
                if client_identifier:
                    error_url += f'&client={client_identifier}'
                return redirect(error_url)

            code = serializer.validated_data.get('code')
            if not code:
                return Response({
                    'error': 'No authorization code provided'
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                # Exchange code for token with client-specific configuration
                oauth_response = SlackOAuthService.exchange_code_for_token(
                    code,
                    client_identifier=client_identifier
                )
                
                if not oauth_response:
                    logger.error("OAuth response is None")
                    return Response({
                        'error': 'OAuth failed',
                        'details': 'No response from Slack OAuth service'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                if not oauth_response.get('ok'):
                    logger.error(f"OAuth failed: {oauth_response}")
                    return Response({
                        'error': 'OAuth failed',
                        'details': oauth_response.get('error', 'Unknown error')
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Get or create admin user for OAuth callback
                admin_user, created = User.objects.get_or_create(
                    username='admin',
                    defaults={'email': 'admin@example.com', 'is_superuser': True, 'is_staff': True}
                )
                
                # Store OAuth data
                slack_user, workspace = SlackOAuthService.store_oauth_data(
                    admin_user, oauth_response
                )
                
                # Sync channels using bot token (more reliable than user token)
                if workspace:
                    logger.info(f"Initiating channel sync for workspace {workspace.team_name}")

                    # Get bot token for syncing channels
                    try:
                        bot = workspace.slackbot
                    except SlackBot.DoesNotExist:
                        bot = None
                    if bot:
                        logger.info(f"Found bot {bot.bot_user_id} for channel sync")

                        # Use enhanced sync_channels with retry logic
                        sync_result = SlackDataService.sync_channels(workspace, bot.bot_access_token, max_retries=3)

                        if sync_result.get('success'):
                            logger.info(f"Channel sync successful for {workspace.team_name}:")
                            logger.info(f"  - Retrieved: {sync_result.get('channels_retrieved', 0)} channels")
                            logger.info(f"  - Created: {sync_result.get('channels_created', 0)} new channels")
                            logger.info(f"  - Updated: {sync_result.get('channels_updated', 0)} existing channels")
                            logger.info(f"  - Total active: {sync_result.get('total_active', 0)} channels in database")
                        else:
                            logger.error(f"Channel sync failed for {workspace.team_name}:")
                            logger.error(f"  - Error: {sync_result.get('error', 'Unknown error')}")
                            logger.error(f"  - Attempts: {sync_result.get('attempts', 0)}")
                            # Continue with OAuth flow even if sync fails

                    else:
                        logger.warning(f"No bot found for workspace {workspace.team_name}, skipping channel sync")
                
                # Redirect to success page
                redirect_url = '/?success=true'
                if workspace:
                    redirect_url += f'&workspace={workspace.team_name}'
                if client_identifier:
                    redirect_url += f'&client={client_identifier}'

                return redirect(redirect_url)
                
            except Exception as e:
                logger.error(f"OAuth callback error: {str(e)}")
                return Response({
                    'error': 'OAuth processing failed',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SlackWorkspacesView(APIView):
    """
    List user's connected Slack workspaces (supports multi-tenant filtering)
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, client_identifier=None):
        """
        Get user's connected workspaces, optionally filtered by client
        """
        # For anonymous users or testing, return workspaces with valid configurations only
        if request.user.is_anonymous:
            workspaces = SlackWorkspace.objects.filter(
                is_active=True,
                app_config__isnull=False,  # Exclude orphaned workspaces
                app_config__is_active=True  # Only active configurations
            )
        else:
            workspaces = SlackDataService.get_user_workspaces(request.user)
            # Also filter out orphaned workspaces for authenticated users (list comprehension since it's a list)
            workspaces = [
                ws for ws in workspaces
                if ws.app_config is not None and ws.app_config.is_active
            ]

        # Filter by client if specified
        if client_identifier:
            try:
                app_config = SlackAppConfiguration.objects.get(
                    client_identifier=client_identifier,
                    is_active=True
                )
                # Handle both queryset and list
                if hasattr(workspaces, 'filter'):
                    # It's a queryset
                    workspaces = workspaces.filter(app_config=app_config)
                else:
                    # It's a list
                    workspaces = [ws for ws in workspaces if ws.app_config == app_config]
            except SlackAppConfiguration.DoesNotExist:
                logger.warning(f"No configuration found for client: {client_identifier}")
                # Handle both queryset and list for empty results
                if hasattr(workspaces, 'none'):
                    workspaces = workspaces.none()
                else:
                    workspaces = []

        serializer = SlackWorkspaceSerializer(workspaces, many=True)

        response_data = {
            'workspaces': serializer.data
        }

        if client_identifier:
            response_data['client_identifier'] = client_identifier

        return Response(response_data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class SlackChannelsView(APIView):
    """
    Slack channels operations
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, client_identifier=None, workspace_id=None):
        """
        List channels for a workspace
        """
        try:
            if workspace_id:
                workspace = SlackWorkspace.objects.get(
                    id=workspace_id,
                    app_config__isnull=False,  # Must have valid configuration
                    app_config__is_active=True
                )
                channels = SlackChannel.objects.filter(workspace=workspace, is_archived=False)
            else:
                # Get channels only from workspaces with valid configurations
                channels = SlackChannel.objects.filter(
                    is_archived=False,
                    workspace__app_config__isnull=False,  # Must have valid configuration
                    workspace__app_config__is_active=True
                )

            serializer = SlackChannelSerializer(channels, many=True)
            return Response({
                'channels': serializer.data
            }, status=status.HTTP_200_OK)
            
        except SlackWorkspace.DoesNotExist:
            return Response({
                'error': 'Workspace not found'
            }, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, client_identifier=None):
        """
        Create a new channel
        """
        serializer = CreateChannelSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Get first available SlackUser (since we allow anonymous access for testing)
                slack_user = SlackUser.objects.filter(
                    is_active=True
                ).first()
                
                if not slack_user:
                    return Response({
                        'error': 'No Slack integration found'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Create channel via Slack API
                slack_service = SlackAPIService(slack_user.access_token)
                result = slack_service.create_channel(
                    name=serializer.validated_data['name'],
                    is_private=serializer.validated_data['is_private']
                )
                
                # Store channel in database
                channel_data = result.get('channel', {})
                if channel_data:
                    channel = SlackChannel.objects.create(
                        workspace=slack_user.workspace,
                        channel_id=channel_data['id'],
                        channel_name=channel_data['name'],
                        channel_type='private_channel' if channel_data.get('is_private') else 'public_channel',
                        is_private=channel_data.get('is_private', False)
                    )
                    
                    return Response({
                        'message': 'Channel created successfully',
                        'channel': SlackChannelSerializer(channel).data
                    }, status=status.HTTP_201_CREATED)
                
                return Response({
                    'error': 'Failed to create channel'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            except Exception as e:
                logger.error(f"Channel creation error: {str(e)}")
                return Response({
                    'error': 'Channel creation failed',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class SlackMessagesView(APIView):
    """
    Slack messages operations
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # Disable all authentication including SessionAuthentication

    def post(self, request, client_identifier=None):
        """
        Send a message to Slack
        """
        serializer = SendMessageSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Handle both authenticated and anonymous users
                if request.user.is_anonymous:
                    # For anonymous users, use bot token for sending messages
                    bot = SlackBot.objects.filter(is_active=True, workspace__app_config__isnull=False).first()
                    if not bot:
                        return Response({
                            'error': 'No Slack bot integration found'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    slack_service = SlackAPIService(bot.bot_access_token)
                else:
                    # For authenticated users, try user token first, fallback to bot token
                    slack_user = SlackUser.objects.filter(
                        user=request.user, is_active=True
                    ).first()

                    if slack_user:
                        slack_service = SlackAPIService(slack_user.access_token)
                    else:
                        # Fallback to bot token
                        bot = SlackBot.objects.filter(is_active=True, workspace__app_config__isnull=False).first()
                        if not bot:
                            return Response({
                                'error': 'No Slack integration found'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        slack_service = SlackAPIService(bot.bot_access_token)
                result = slack_service.send_message(
                    channel=serializer.validated_data['channel'],
                    text=serializer.validated_data['text'],
                    thread_ts=serializer.validated_data.get('thread_ts')
                )
                
                return Response({
                    'message': 'Message sent successfully',
                    'slack_response': result
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Message sending error: {str(e)}")
                return Response({
                    'error': 'Message sending failed',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class SlackFilesView(APIView):
    """
    Slack file operations
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, client_identifier=None):
        """
        Upload file to Slack
        """
        serializer = UploadFileSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Get user's Slack token
                slack_user = SlackUser.objects.filter(
                    user=request.user, is_active=True
                ).first()
                
                if not slack_user:
                    return Response({
                        'error': 'No Slack integration found'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Upload file via Slack API
                slack_service = SlackAPIService(slack_user.access_token)
                
                if serializer.validated_data.get('file'):
                    file_obj = serializer.validated_data['file']
                    result = slack_service.upload_file(
                        channels=serializer.validated_data['channels'],
                        file_path=None,  # We'll handle file object separately
                        content=file_obj.read(),
                        filename=serializer.validated_data.get('filename', file_obj.name),
                        title=serializer.validated_data.get('title')
                    )
                else:
                    result = slack_service.upload_file(
                        channels=serializer.validated_data['channels'],
                        content=serializer.validated_data['content'],
                        filename=serializer.validated_data.get('filename', 'file.txt'),
                        title=serializer.validated_data.get('title')
                    )
                
                return Response({
                    'message': 'File uploaded successfully',
                    'slack_response': result
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"File upload error: {str(e)}")
                return Response({
                    'error': 'File upload failed',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SlackChannelJoinView(APIView):
    """
    Join a Slack channel
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, client_identifier=None):
        """
        Join a channel
        """
        serializer = JoinChannelSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Get user's Slack token
                slack_user = SlackUser.objects.filter(
                    user=request.user, is_active=True
                ).first()
                
                if not slack_user:
                    return Response({
                        'error': 'No Slack integration found'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Join channel via Slack API
                slack_service = SlackAPIService(slack_user.access_token)
                result = slack_service.join_channel(
                    channel=serializer.validated_data['channel']
                )
                
                return Response({
                    'message': 'Channel joined successfully',
                    'slack_response': result
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Channel join error: {str(e)}")
                return Response({
                    'error': 'Channel join failed',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SlackReactionView(APIView):
    """
    Add reactions to Slack messages
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, client_identifier=None):
        """
        Add reaction to a message
        """
        serializer = AddReactionSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Get user's Slack token
                slack_user = SlackUser.objects.filter(
                    user=request.user, is_active=True
                ).first()
                
                if not slack_user:
                    return Response({
                        'error': 'No Slack integration found'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Add reaction via Slack API
                slack_service = SlackAPIService(slack_user.access_token)
                result = slack_service.add_reaction(
                    channel=serializer.validated_data['channel'],
                    timestamp=serializer.validated_data['timestamp'],
                    name=serializer.validated_data['name']
                )
                
                return Response({
                    'message': 'Reaction added successfully',
                    'slack_response': result
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Reaction add error: {str(e)}")
                return Response({
                    'error': 'Reaction add failed',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])  # Allow access without authentication for now
@csrf_exempt
def slack_user_info(request):
    """
    Get Slack user information
    """
    try:
        # Get the bot token from workspaces with valid configurations only
        slack_bot = SlackBot.objects.filter(
            bot_access_token__isnull=False,
            workspace__app_config__isnull=False,
            workspace__app_config__is_active=True
        ).first()

        if not slack_bot:
            return Response({
                'error': 'No Slack integration found'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get the Slack user ID from the admin user's integration
        slack_user = SlackUser.objects.filter(
            workspace=slack_bot.workspace,
            is_active=True,
            workspace__app_config__isnull=False,
            workspace__app_config__is_active=True
        ).first()
        
        # For now, return the stored user information instead of calling Slack API
        if slack_user:
            user_info = {
                'ok': True,
                'user': {
                    'id': slack_user.slack_user_id,
                    'name': f'User {slack_user.slack_user_id}',
                    'real_name': 'Slack User',
                    'email': 'user@slack.com'  # placeholder
                }
            }
        else:
            user_info = {
                'ok': True,
                'user': {
                    'id': 'unknown',
                    'name': 'Unknown User',
                    'real_name': 'Unknown User'
                }
            }
        
        return Response({
            'user_info': user_info
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"User info error: {str(e)}")
        return Response({
            'error': 'Failed to get user info',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SlackBulkJoinChannelsView(APIView):
    """
    Bulk join all available public channels using bot token
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, client_identifier=None):
        """
        Join all available public channels
        """
        try:
            # Get bot token from workspaces with valid configurations only
            slack_bot = SlackBot.objects.filter(
                is_active=True,
                workspace__app_config__isnull=False,
                workspace__app_config__is_active=True
            ).first()

            if not slack_bot:
                return Response({
                    'error': 'No active Slack bot found'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Use bot token for bulk joining
            slack_service = SlackAPIService(slack_bot.bot_access_token)
            results = slack_service.bulk_join_channels()

            return Response({
                'message': 'Bulk channel join completed',
                'results': results,
                'summary': {
                    'joined': len(results['joined']),
                    'already_joined': len(results['already_joined']),
                    'private_channels': len(results['private_channels']),
                    'failed': len(results['failed'])
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Bulk channel join error: {str(e)}")
            return Response({
                'error': 'Bulk channel join failed',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class SlackMessagesReadView(APIView):
    """
    Read messages from Slack channels
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, client_identifier=None):
        """
        Read messages from a specific channel or all channels
        """
        # Determine if this is a read-all operation based on URL path
        is_read_all = 'read/all' in request.path

        if is_read_all:
            serializer = ReadAllChannelsMessagesSerializer(data=request.GET)
        else:
            serializer = ReadMessagesSerializer(data=request.GET, context={'view': self})

        if serializer.is_valid():
            try:
                # Get bot token for reading messages - only from workspaces with valid configurations
                slack_bot = SlackBot.objects.filter(
                    is_active=True,
                    workspace__app_config__isnull=False,
                    workspace__app_config__is_active=True
                ).first()

                if not slack_bot:
                    return Response({
                        'error': 'No active Slack bot found'
                    }, status=status.HTTP_400_BAD_REQUEST)

                slack_service = SlackAPIService(slack_bot.bot_access_token)

                if is_read_all:
                    # Read from all accessible channels
                    result = slack_service.get_all_accessible_channels_messages(
                        limit_per_channel=serializer.validated_data.get('limit_per_channel', 20),
                        oldest=serializer.validated_data.get('oldest'),
                        latest=serializer.validated_data.get('latest'),
                        channel_types=serializer.validated_data.get('channel_types', 'public_channel,private_channel')
                    )

                    return Response({
                        'message': 'Messages retrieved from all accessible channels',
                        'data': result
                    }, status=status.HTTP_200_OK)

                else:
                    # Read from specific channel
                    channel = serializer.validated_data['channel']
                    result = slack_service.get_channel_history(
                        channel=channel,
                        limit=serializer.validated_data.get('limit', 50),
                        oldest=serializer.validated_data.get('oldest'),
                        latest=serializer.validated_data.get('latest'),
                        cursor=serializer.validated_data.get('cursor'),
                        include_all_metadata=serializer.validated_data.get('include_all_metadata', False)
                    )

                    return Response({
                        'message': f'Messages retrieved from channel {channel}',
                        'data': result
                    }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Message reading error: {str(e)}")
                return Response({
                    'error': 'Failed to read messages',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GenericSlackOAuthView(APIView):
    """
    Generic Slack OAuth redirect - automatically redirects to Slack OAuth with first available app configuration
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Redirect directly to Slack OAuth using the first available app configuration
        """
        try:
            # Get the first available Slack app configuration
            from apps.core.models import SlackAppConfiguration
            config = SlackAppConfiguration.objects.first()

            if not config:
                return Response({
                    'error': 'No Slack app configuration found',
                    'message': 'Please configure a Slack app first'
                }, status=status.HTTP_404_NOT_FOUND)

            # Get state parameter if provided
            state = request.GET.get('state', '')

            # Get the actual client_id - try decryption but handle all cases
            client_id = config.client_id

            # Check if this looks like an encrypted value vs a real client_id
            if len(client_id) > 50 and not '.' in client_id:
                # This looks encrypted, try to decrypt
                try:
                    from cryptography.fernet import Fernet, InvalidToken
                    from django.conf import settings
                    import base64

                    fernet = Fernet(settings.SLACK_ENCRYPTION_KEY)
                    encrypted_data = base64.urlsafe_b64decode(client_id.encode())
                    decrypted_bytes = fernet.decrypt(encrypted_data)
                    decrypted_client_id = decrypted_bytes.decode()

                    # Validate decrypted client_id format (should be like 1234567890.1234567890)
                    if '.' in decrypted_client_id and len(decrypted_client_id.split('.')) == 2:
                        client_id = decrypted_client_id
                        logger.info(f"Successfully decrypted client_id: {client_id}")
                    else:
                        logger.warning(f"Decrypted client_id has invalid format: {decrypted_client_id}")
                        raise ValueError("Invalid decrypted client_id format")

                except (InvalidToken, ValueError, Exception) as e:
                    # Decryption failed - this means the stored data is corrupted or encrypted with wrong key
                    logger.error(f"Cannot decrypt client_id: {str(e)}")
                    return Response({
                        'error': 'Configuration error',
                        'message': 'The Slack app client_id cannot be decrypted. Please update your configuration with the correct credentials.',
                        'action': 'Go to /api/slack/config/testapp/ and enter your real Slack app credentials',
                        'debug': f'Stored client_id: {client_id[:50]}... (encrypted)',
                        'expected_format': 'Client ID should look like: 1234567890.1234567890'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Final validation - ensure client_id looks correct
            if not ('.' in client_id and len(client_id.split('.')) == 2):
                logger.error(f"Client ID has invalid format: {client_id}")
                return Response({
                    'error': 'Invalid client_id format',
                    'message': 'The client_id must be in Slack format (e.g., 1234567890.1234567890)',
                    'current_client_id': client_id,
                    'action': 'Update your configuration with the correct Slack app Client ID'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Build the Slack OAuth URL
            from urllib.parse import urlencode

            base_url = "https://slack.com/oauth/v2/authorize"
            params = {
                'client_id': client_id,
                'scope': config.scopes,
                'redirect_uri': f"{request.scheme}://{request.get_host()}/api/slack/auth/callback/",
            }

            if state:
                params['state'] = state

            # Build query string with proper URL encoding
            query_string = urlencode(params)
            oauth_url = f"{base_url}?{query_string}"

            # Direct redirect to Slack
            return redirect(oauth_url)

        except Exception as e:
            logger.error(f"Generic OAuth redirect error: {str(e)}")
            return Response({
                'error': 'OAuth redirect failed',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Direct Message Views

@method_decorator(csrf_exempt, name='dispatch')
class SlackDMView(APIView):
    """
    API view for sending direct messages (CSRF exempt for API testing)
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, client_identifier=None):
        """
        Send a direct message to a user
        """
        try:
            serializer = SendDMSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Get bot token for API calls
            bot = SlackBot.objects.filter(workspace__app_config__isnull=False).first()
            if not bot:
                return Response({
                    'error': 'No Slack bot configuration found. Please complete OAuth flow first.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Initialize Slack API service
            slack_service = SlackAPIService(bot.bot_access_token)

            # Send DM
            response = slack_service.send_dm(
                user_id=serializer.validated_data['user_id'],
                text=serializer.validated_data['text'],
                thread_ts=serializer.validated_data.get('thread_ts'),
                as_user=serializer.validated_data.get('as_user', True)
            )

            return Response({
                'success': True,
                'message': 'Direct message sent successfully',
                'data': response
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Failed to send DM: {str(e)}")
            return Response({
                'error': 'Failed to send direct message',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class SlackDMReadView(APIView):
    """
    API view for reading direct messages (CSRF exempt for API testing)
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, client_identifier=None):
        """
        Read direct messages from a specific DM or all DMs
        """
        try:
            # Check if this is a request for all DMs
            read_all = request.path.endswith('/all/') or request.GET.get('read_all') == 'true'

            if read_all:
                serializer = ReadAllDMsSerializer(data=request.GET)
            else:
                serializer = ReadDMSerializer(data=request.GET)

            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Try to get user token first for accessing real human DM conversations
            user_token = None
            slack_user = SlackUser.objects.filter(is_active=True).first()
            if slack_user and slack_user.access_token:
                user_token = slack_user.access_token
                logger.info(f"Using user token for DM reading (user: {slack_user.slack_user_id})")
                slack_service = SlackAPIService(user_token)
                token_type = 'user'
            else:
                # Fallback to bot token (will only show bot conversations)
                bot = SlackBot.objects.filter(workspace__app_config__isnull=False).first()
                if not bot:
                    return Response({
                        'error': 'No Slack bot or user configuration found. Please complete OAuth flow first.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                logger.info("Using bot token for DM reading (limited to bot conversations)")
                slack_service = SlackAPIService(bot.bot_access_token)
                token_type = 'bot'

            if read_all:
                # Read from all DM conversations
                response = slack_service.get_all_dm_messages(
                    limit_per_dm=serializer.validated_data.get('limit_per_dm', 20),
                    oldest=serializer.validated_data.get('oldest'),
                    latest=serializer.validated_data.get('latest')
                )
                return Response(response, status=status.HTTP_200_OK)
            else:
                # Read from specific DM
                dm_channel = serializer.validated_data.get('dm_channel')
                user_id = serializer.validated_data.get('user_id')

                # If user_id provided, find existing DM conversation (no scope issues)
                if user_id and not dm_channel:
                    logger.info(f"Looking for existing DM channel with user {user_id}")
                    dm_channel = slack_service.find_dm_channel_with_user(user_id)

                    if not dm_channel:
                        logger.info(f"No existing DM conversation found with user {user_id}")
                        return Response({
                            'error': f'No existing DM conversation found with user {user_id}',
                            'details': 'User must have previously messaged with the bot or other users for DM history to be accessible',
                            'token_type': token_type
                        }, status=status.HTTP_404_NOT_FOUND)

                    logger.info(f"Found DM channel: {dm_channel}")

                if not dm_channel:
                    return Response({
                        'error': 'Could not determine DM channel'
                    }, status=status.HTTP_400_BAD_REQUEST)

                response = slack_service.get_dm_history(
                    channel=dm_channel,
                    limit=serializer.validated_data.get('limit', 50),
                    oldest=serializer.validated_data.get('oldest'),
                    latest=serializer.validated_data.get('latest'),
                    cursor=serializer.validated_data.get('cursor')
                )

                # Add token type info to response for debugging
                response['token_type'] = token_type
                response['debug_info'] = f"Using {token_type} token for DM access"

                return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Failed to read DMs: {str(e)}")
            return Response({
                'error': 'Failed to read direct messages',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class SlackDMUsersView(APIView):
    """
    API view for listing workspace users (CSRF exempt for API testing)
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, client_identifier=None):
        """
        Get list of workspace users for DM recipient selection
        """
        try:
            # Get bot token for API calls - only from workspaces with valid configurations
            bot = SlackBot.objects.filter(
                workspace__isnull=False,
                workspace__app_config__isnull=False,
                workspace__app_config__is_active=True
            ).first()
            if not bot:
                return Response({
                    'error': 'No Slack bot configuration found. Please complete OAuth flow first.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Initialize Slack API service
            slack_service = SlackAPIService(bot.bot_access_token)

            # Get workspace users
            users = slack_service.list_workspace_users(
                limit=int(request.GET.get('limit', 200))
            )

            return Response({
                'users': users,
                'count': len(users)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Failed to list users: {str(e)}")
            return Response({
                'error': 'Failed to list workspace users',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class SlackDMConversationsView(APIView):
    """
    API view for listing DM conversations (CSRF exempt for API testing)
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, client_identifier=None):
        """
        Get list of DM conversations
        """
        try:
            # Get bot token for API calls - only from workspaces with valid configurations
            bot = SlackBot.objects.filter(
                workspace__isnull=False,
                workspace__app_config__isnull=False,
                workspace__app_config__is_active=True
            ).first()
            if not bot:
                return Response({
                    'error': 'No Slack bot configuration found. Please complete OAuth flow first.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Initialize Slack API service
            slack_service = SlackAPIService(bot.bot_access_token)

            # Get DM conversations
            conversations = slack_service.list_dm_conversations()

            # Enhance conversation data with user info if available
            for conv in conversations:
                if conv.get('user'):
                    try:
                        user_info = slack_service.get_user_info(conv['user'])
                        conv['user_info'] = {
                            'name': user_info.get('user', {}).get('name'),
                            'real_name': user_info.get('user', {}).get('real_name'),
                            'display_name': user_info.get('user', {}).get('profile', {}).get('display_name'),
                            'image': user_info.get('user', {}).get('profile', {}).get('image_48')
                        }
                    except:
                        # If we can't get user info, skip it
                        pass

            return Response({
                'conversations': conversations,
                'count': len(conversations)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Failed to list DM conversations: {str(e)}")
            return Response({
                'error': 'Failed to list DM conversations',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)