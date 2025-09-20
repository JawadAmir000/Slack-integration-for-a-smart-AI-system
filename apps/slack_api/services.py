"""
Slack API service layer for handling Slack API interactions
"""

import logging
import requests
from typing import Dict, Any, Optional, List
from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from apps.core.models import SlackUser, SlackWorkspace, SlackBot, SlackChannel, SlackAppConfiguration

logger = logging.getLogger('slack_api')


class SlackOAuthService:
    """
    Service for handling Slack OAuth 2.0 flow with multi-tenant support
    """

    @staticmethod
    def get_app_config(client_identifier: str = None) -> Optional[SlackAppConfiguration]:
        """
        Get Slack app configuration for a client
        """
        if not client_identifier:
            client_identifier = settings.SLACK_DEFAULT_CLIENT_ID

        try:
            config = SlackAppConfiguration.objects.get(
                client_identifier=client_identifier,
                is_active=True
            )
            config.increment_usage()
            return config
        except SlackAppConfiguration.DoesNotExist:
            logger.warning(f"No configuration found for client: {client_identifier}")
            return None

    @staticmethod
    def get_primary_config() -> Optional[SlackAppConfiguration]:
        """
        Get the primary active Slack app configuration
        Priority: Most recently created active configuration
        """
        try:
            config = SlackAppConfiguration.objects.filter(
                is_active=True
            ).order_by('-created_at').first()

            if config:
                logger.info(f"Using primary configuration: {config.client_identifier} ({config.client_name})")
                config.increment_usage()
                return config
            else:
                logger.warning("No active configurations found in database")
                return None
        except Exception as e:
            logger.error(f"Error getting primary configuration: {e}")
            return None

    @staticmethod
    def get_fallback_config() -> Dict[str, str]:
        """
        Get fallback configuration - first tries database config, then settings (legacy support)
        """
        # Try to get first available configuration from database
        try:
            from apps.core.models import SlackAppConfiguration
            first_config = SlackAppConfiguration.objects.first()
            if first_config:
                return {
                    'client_id': first_config.client_id,
                    'client_secret': first_config.client_secret,
                    'signing_secret': first_config.signing_secret,
                    'redirect_uri': settings.SLACK_REDIRECT_URI.replace('{client_identifier}', 'auth') if '{client_identifier}' in settings.SLACK_REDIRECT_URI else settings.SLACK_REDIRECT_URI,
                    'scopes': first_config.scopes
                }
        except Exception as e:
            logger.warning(f"Could not load database configuration for fallback: {e}")

        # Fallback to hardcoded values (since database config was deleted)
        return {
            'client_id': '9521493598272.9538323153873',
            'client_secret': 'be6326e2e135ad14020a8a7d126447ae',
            'signing_secret': 'your-signing-secret',  # Not needed for OAuth exchange
            'redirect_uri': 'https://46550c9cd1eb.ngrok-free.app/api/slack/auth/callback',
            'scopes': 'channels:read,groups:read,im:read,mpim:read,chat:write,files:write,users:read,im:write,mpim:write,users:read.email,channels:history,groups:history,im:history,mpim:history,channels:join,groups:write',
            'user_scopes': 'channels:read,groups:read,im:read,mpim:read,im:history,mpim:history,groups:history,users:read'
        }

    @staticmethod
    def get_authorization_url_for_config(config: SlackAppConfiguration, state: str = None) -> str:
        """
        Generate Slack OAuth authorization URL for specific configuration
        """
        base_url = "https://slack.com/oauth/v2/authorize"

        from urllib.parse import urlencode

        # TEMPORARY FIX: Use actual client_id value since decryption isn't working
        if config.client_identifier == 'newone':
            client_id = '9521493598272.9538323153873'
        else:
            client_id = config.client_id

        params = {
            'client_id': client_id,
            'scope': ','.join(config.get_scopes_list()),
            'redirect_uri': config.redirect_uri,
            'user_scope': 'im:read,im:history,users:read',  # Add user token scopes for DM access
        }

        if state:
            params['state'] = state

        # Use proper URL encoding
        query_string = urlencode(params)
        return f"{base_url}?{query_string}"

    @staticmethod
    def get_authorization_url(state: str = None, client_identifier: str = None) -> str:
        """
        Generate Slack OAuth authorization URL (supports both multi-tenant and legacy)
        """
        # Try to get client-specific configuration
        if client_identifier:
            config = SlackOAuthService.get_app_config(client_identifier)
            if config:
                return SlackOAuthService.get_authorization_url_for_config(config, state)

        # Fallback to legacy configuration
        base_url = "https://slack.com/oauth/v2/authorize"
        fallback_config = SlackOAuthService.get_fallback_config()

        from urllib.parse import urlencode

        params = {
            'client_id': fallback_config['client_id'],
            'scope': fallback_config['scopes'],
            'redirect_uri': fallback_config['redirect_uri'],
            'user_scope': 'im:read,im:history,users:read',  # Add user token scopes for DM access
        }

        if state:
            params['state'] = state

        # Use proper URL encoding
        query_string = urlencode(params)
        return f"{base_url}?{query_string}"

    @staticmethod
    def get_auto_authorization_url(state: str = None) -> tuple[str, str]:
        """
        Generate Slack OAuth authorization URL using primary configuration
        Returns: (auth_url, client_identifier)
        """
        # Try to get primary configuration from database
        primary_config = SlackOAuthService.get_primary_config()
        if primary_config:
            auth_url = SlackOAuthService.get_authorization_url_for_config(primary_config, state)
            return auth_url, primary_config.client_identifier

        # Fallback to legacy configuration
        logger.info("No primary configuration found, falling back to legacy settings")
        auth_url = SlackOAuthService.get_authorization_url(state=state, client_identifier=None)
        return auth_url, None

    @staticmethod
    def exchange_code_for_token(code: str, client_identifier: str = None) -> Dict[str, Any]:
        """
        Exchange OAuth code for access token (supports multi-tenant configurations)
        """
        try:
            logger.info(f"Exchanging OAuth code: {code[:20]}... for client: {client_identifier}")

            # Try to get client-specific configuration
            config = None
            if client_identifier:
                config = SlackOAuthService.get_app_config(client_identifier)
            else:
                # If no client_identifier provided, try to find config by checking primary config
                logger.info("No client_identifier provided, trying to find primary configuration")
                config = SlackOAuthService.get_primary_config()

            # Use client config or fallback to legacy settings
            if config:
                # TEMPORARY FIX: Use actual client_id/secret values since decryption isn't working
                if config.client_identifier == 'newone':
                    logger.info("Using hardcoded values for 'newone' config due to decryption issues")
                    client_id = '9521493598272.9538323153873'
                    client_secret = 'be6326e2e135ad14020a8a7d126447ae'
                    redirect_uri = config.redirect_uri
                else:
                    client_id = config.client_id
                    client_secret = config.client_secret
                    redirect_uri = config.redirect_uri
                logger.info(f"Using configuration for client: {client_identifier}")
            else:
                fallback_config = SlackOAuthService.get_fallback_config()
                client_id = fallback_config['client_id']
                client_secret = fallback_config['client_secret']
                redirect_uri = fallback_config['redirect_uri']
                logger.info("Using fallback configuration")

            response = requests.post(
                'https://slack.com/api/oauth.v2.access',
                data={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'code': code,
                    'redirect_uri': redirect_uri,
                }
            )

            logger.info(f"Slack OAuth response status: {response.status_code}")
            response.raise_for_status()

            json_response = response.json()
            logger.info(f"Slack OAuth response: {json_response}")

            # Add client config to response for later use
            if config:
                json_response['_client_config'] = config

            return json_response

        except requests.RequestException as e:
            logger.error(f"Failed to exchange OAuth code: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response content: {e.response.text}")
            raise Exception(f"OAuth token exchange failed: {str(e)}")
    
    @staticmethod
    def store_oauth_data(user, oauth_response: Dict[str, Any]) -> tuple:
        """
        Store OAuth response data in database (with multi-tenant support)
        """
        try:
            # Extract team/workspace information
            team_data = oauth_response.get('team', {})

            # Get client configuration if provided
            app_config = oauth_response.get('_client_config')

            # Create or update workspace
            workspace_defaults = {
                'team_name': team_data.get('name'),
                'team_domain': team_data.get('domain'),
                'team_url': (oauth_response.get('enterprise') or {}).get('url') or f"https://{team_data.get('domain', 'workspace')}.slack.com"
            }

            # Associate with app config if available
            if app_config:
                workspace_defaults['app_config'] = app_config

            workspace, created = SlackWorkspace.objects.get_or_create(
                team_id=team_data.get('id'),
                defaults=workspace_defaults
            )

            # If workspace already existed but didn't have app_config, update it
            if not created and app_config and not workspace.app_config:
                workspace.app_config = app_config
                workspace.save()
            
            # Store bot token if available
            if oauth_response.get('access_token') and oauth_response.get('token_type') == 'bot':
                SlackBot.objects.update_or_create(
                    workspace=workspace,
                    defaults={
                        'bot_user_id': oauth_response.get('bot_user_id'),
                        'bot_access_token': oauth_response.get('access_token'),
                        'bot_scopes': oauth_response.get('scope', ''),
                        'app_id': oauth_response.get('app_id')
                    }
                )
            
            # Store user token if available
            authed_user = oauth_response.get('authed_user', {})
            logger.info(f"Processing authed_user from OAuth response: {authed_user}")

            if authed_user and authed_user.get('id'):
                user_access_token = authed_user.get('access_token', '')
                logger.info(f"User access token present: {bool(user_access_token)}")
                logger.info(f"Creating/updating SlackUser for user_id: {authed_user.get('id')}")

                slack_user, user_created = SlackUser.objects.update_or_create(
                    user=user,
                    workspace=workspace,
                    slack_user_id=authed_user.get('id'),
                    defaults={
                        'access_token': user_access_token,
                        'refresh_token': authed_user.get('refresh_token'),
                        'scopes': authed_user.get('scope', ''),
                    }
                )

                if user_created:
                    logger.info(f"Created new SlackUser: {slack_user.slack_user_id}")
                else:
                    logger.info(f"Updated existing SlackUser: {slack_user.slack_user_id}")

                if not user_access_token:
                    logger.warning(f"SlackUser {slack_user.slack_user_id} created without access token - app may need user token scopes configured")

                return slack_user, workspace
            
            return None, workspace
            
        except Exception as e:
            logger.error(f"Failed to store OAuth data: {str(e)}")
            raise Exception(f"Failed to store OAuth data: {str(e)}")


class SlackAPIService:
    """
    Service for interacting with Slack Web API
    """
    
    def __init__(self, token: str):
        self.client = WebClient(token=token)
        self.token = token
    
    def test_auth(self) -> Dict[str, Any]:
        """
        Test API authentication
        """
        try:
            response = self.client.auth_test()
            return response.data
        except SlackApiError as e:
            logger.error(f"Auth test failed: {e.response['error']}")
            raise Exception(f"Auth test failed: {e.response['error']}")
    
    def get_user_info(self, user_id: str = None) -> Dict[str, Any]:
        """
        Get user information
        """
        try:
            if user_id:
                response = self.client.users_info(user=user_id)
            else:
                response = self.client.auth_test()
            return response.data
        except SlackApiError as e:
            logger.error(f"Failed to get user info: {e.response['error']}")
            raise Exception(f"Failed to get user info: {e.response['error']}")
    
    def list_channels(self, types: str = "public_channel,private_channel") -> List[Dict[str, Any]]:
        """
        List channels in workspace
        """
        try:
            response = self.client.conversations_list(
                types=types,
                exclude_archived=True
            )
            return response.data.get('channels', [])
        except SlackApiError as e:
            logger.error(f"Failed to list channels: {e.response['error']}")
            raise Exception(f"Failed to list channels: {e.response['error']}")
    
    def send_message(self, channel: str, text: str, **kwargs) -> Dict[str, Any]:
        """
        Send a message to a channel with auto-join capability
        """
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text,
                **kwargs
            )
            return response.data
        except SlackApiError as e:
            error_code = e.response['error']

            # If bot is not in channel, try to join it first
            if error_code == 'not_in_channel':
                logger.info(f"Bot not in channel {channel}, attempting to join...")
                try:
                    # Try to join the channel
                    join_response = self.client.conversations_join(channel=channel)
                    logger.info(f"Successfully joined channel {channel}")

                    # Retry sending the message after joining
                    response = self.client.chat_postMessage(
                        channel=channel,
                        text=text,
                        **kwargs
                    )
                    return response.data

                except SlackApiError as join_error:
                    join_error_code = join_error.response['error']
                    if join_error_code == 'channel_not_found':
                        logger.error(f"Channel {channel} not found")
                        raise Exception(f"Channel not found: {channel}")
                    elif join_error_code == 'is_private':
                        logger.error(f"Cannot join private channel {channel}")
                        raise Exception(f"Cannot join private channel: {channel}. Bot must be invited by a channel member.")
                    elif join_error_code == 'already_in_channel':
                        # This shouldn't happen, but retry sending message
                        logger.info(f"Bot already in channel {channel}, retrying message...")
                        try:
                            response = self.client.chat_postMessage(
                                channel=channel,
                                text=text,
                                **kwargs
                            )
                            return response.data
                        except SlackApiError as retry_error:
                            logger.error(f"Failed to send message after join: {retry_error.response['error']}")
                            raise Exception(f"Failed to send message: {retry_error.response['error']}")
                    else:
                        logger.error(f"Failed to join channel {channel}: {join_error_code}")
                        raise Exception(f"Failed to join channel: {join_error_code}")
            else:
                logger.error(f"Failed to send message: {error_code}")
                raise Exception(f"Failed to send message: {error_code}")
    
    def upload_file(self, channels: str, file_path: str = None, content: str = None, 
                    filename: str = None, title: str = None) -> Dict[str, Any]:
        """
        Upload file to Slack (using new 2025 API methods)
        """
        try:
            if file_path:
                with open(file_path, 'rb') as file_content:
                    response = self.client.files_upload_v2(
                        channel=channels,
                        file=file_content,
                        filename=filename or file_path.split('/')[-1],
                        title=title
                    )
            elif content:
                response = self.client.files_upload_v2(
                    channel=channels,
                    content=content,
                    filename=filename or 'file.txt',
                    title=title
                )
            else:
                raise ValueError("Either file_path or content must be provided")
                
            return response.data
        except SlackApiError as e:
            logger.error(f"Failed to upload file: {e.response['error']}")
            raise Exception(f"Failed to upload file: {e.response['error']}")
    
    def get_channel_history(self, channel: str, limit: int = 100, oldest: str = None,
                           latest: str = None, cursor: str = None, include_all_metadata: bool = False) -> Dict[str, Any]:
        """
        Get channel message history with enhanced parameters

        Args:
            channel: Channel ID or name
            limit: Number of messages to retrieve (max 1000)
            oldest: Start of time range (timestamp)
            latest: End of time range (timestamp)
            cursor: Pagination cursor
            include_all_metadata: Include additional message metadata

        Returns:
            Dict containing messages and pagination info
        """
        try:
            params = {
                'channel': channel,
                'limit': min(limit, 1000),  # Slack API max limit
                'include_all_metadata': include_all_metadata
            }

            if oldest:
                params['oldest'] = oldest
            if latest:
                params['latest'] = latest
            if cursor:
                params['cursor'] = cursor

            response = self.client.conversations_history(**params)

            return {
                'messages': response.data.get('messages', []),
                'has_more': response.data.get('has_more', False),
                'response_metadata': response.data.get('response_metadata', {}),
                'channel': channel,
                'ok': response.data.get('ok', True)
            }
        except SlackApiError as e:
            logger.error(f"Failed to get channel history for {channel}: {e.response['error']}")
            raise Exception(f"Failed to get channel history: {e.response['error']}")

    def get_messages_from_multiple_channels(self, channels: List[str], limit_per_channel: int = 50,
                                          oldest: str = None, latest: str = None) -> Dict[str, Any]:
        """
        Get messages from multiple channels

        Args:
            channels: List of channel IDs or names
            limit_per_channel: Number of messages per channel
            oldest: Start of time range (timestamp)
            latest: End of time range (timestamp)

        Returns:
            Dict with messages organized by channel
        """
        results = {
            'channels': {},
            'successful_channels': [],
            'failed_channels': [],
            'total_messages': 0
        }

        for channel in channels:
            try:
                channel_data = self.get_channel_history(
                    channel=channel,
                    limit=limit_per_channel,
                    oldest=oldest,
                    latest=latest
                )

                results['channels'][channel] = channel_data
                results['successful_channels'].append(channel)
                results['total_messages'] += len(channel_data.get('messages', []))

                logger.info(f"Retrieved {len(channel_data.get('messages', []))} messages from channel {channel}")

            except Exception as e:
                error_msg = str(e)
                results['failed_channels'].append({
                    'channel': channel,
                    'error': error_msg
                })
                logger.error(f"Failed to get messages from channel {channel}: {error_msg}")

        return results

    def get_all_accessible_channels_messages(self, limit_per_channel: int = 20,
                                           oldest: str = None, latest: str = None,
                                           channel_types: str = "public_channel,private_channel") -> Dict[str, Any]:
        """
        Get messages from all accessible channels in the workspace

        Args:
            limit_per_channel: Number of messages per channel
            oldest: Start of time range (timestamp)
            latest: End of time range (timestamp)
            channel_types: Types of channels to include

        Returns:
            Dict with messages from all accessible channels
        """
        try:
            # First, get list of all accessible channels
            channels_list = self.list_channels(types=channel_types)
            channel_ids = [channel['id'] for channel in channels_list]

            logger.info(f"Found {len(channel_ids)} accessible channels")

            # Get messages from all channels
            result = self.get_messages_from_multiple_channels(
                channels=channel_ids,
                limit_per_channel=limit_per_channel,
                oldest=oldest,
                latest=latest
            )

            # Add channel metadata
            result['channels_metadata'] = {
                channel['id']: {
                    'name': channel.get('name'),
                    'is_private': channel.get('is_private', False),
                    'is_archived': channel.get('is_archived', False),
                    'topic': channel.get('topic', {}).get('value', ''),
                    'purpose': channel.get('purpose', {}).get('value', '')
                }
                for channel in channels_list
            }

            result['summary'] = {
                'total_channels_found': len(channel_ids),
                'successful_channels': len(result['successful_channels']),
                'failed_channels': len(result['failed_channels']),
                'total_messages_retrieved': result['total_messages']
            }

            return result

        except Exception as e:
            logger.error(f"Failed to get messages from all channels: {str(e)}")
            raise Exception(f"Failed to get messages from all channels: {str(e)}")
    
    def join_channel(self, channel: str) -> Dict[str, Any]:
        """
        Join a channel
        """
        try:
            response = self.client.conversations_join(channel=channel)
            return response.data
        except SlackApiError as e:
            logger.error(f"Failed to join channel: {e.response['error']}")
            raise Exception(f"Failed to join channel: {e.response['error']}")
    
    def create_channel(self, name: str, is_private: bool = False) -> Dict[str, Any]:
        """
        Create a new channel
        """
        try:
            response = self.client.conversations_create(
                name=name,
                is_private=is_private
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Failed to create channel: {e.response['error']}")
            raise Exception(f"Failed to create channel: {e.response['error']}")
    
    def add_reaction(self, channel: str, timestamp: str, name: str) -> Dict[str, Any]:
        """
        Add emoji reaction to a message
        """
        try:
            response = self.client.reactions_add(
                channel=channel,
                timestamp=timestamp,
                name=name
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Failed to add reaction: {e.response['error']}")
            raise Exception(f"Failed to add reaction: {e.response['error']}")

    # Direct Message Methods

    def open_dm_conversation(self, user_id: str) -> Dict[str, Any]:
        """
        Open a direct message conversation with a user

        Args:
            user_id: Slack user ID to open DM with

        Returns:
            Dict containing conversation info including channel ID
        """
        try:
            # Validate user_id format
            if not user_id or not isinstance(user_id, str):
                raise Exception("Invalid user_id: must be a non-empty string")

            # Try to open conversation
            response = self.client.conversations_open(users=user_id)

            if not response.data.get('ok'):
                error_msg = response.data.get('error', 'unknown_error')
                logger.error(f"Slack API returned error for user {user_id}: {error_msg}")
                raise Exception(f"Failed to open DM conversation: {error_msg}")

            return response.data

        except SlackApiError as e:
            error_msg = e.response.get('error', 'unknown_error') if e.response else 'network_error'

            # Provide specific error messages
            if error_msg == 'user_not_found':
                logger.error(f"User {user_id} not found in workspace")
                raise Exception(f"User not found: {user_id}. Please ensure the user exists in this Slack workspace.")
            elif error_msg == 'missing_scope':
                logger.error(f"Missing required OAuth scopes for DM conversation")
                raise Exception("Missing required OAuth scopes. Please re-authorize the app with updated permissions.")
            elif error_msg == 'channel_not_found':
                logger.error(f"DM channel could not be created for user {user_id}")
                raise Exception("Could not create DM conversation. User may have restricted DMs.")
            else:
                logger.error(f"Failed to open DM conversation with {user_id}: {error_msg}")
                raise Exception(f"Failed to open DM conversation: {error_msg}")
        except Exception as e:
            if "Failed to open DM conversation:" in str(e):
                raise
            logger.error(f"Unexpected error opening DM with {user_id}: {str(e)}")
            raise Exception(f"Unexpected error opening DM conversation: {str(e)}")

    def list_dm_conversations(self, types: str = "im,mpim") -> List[Dict[str, Any]]:
        """
        List direct message conversations

        Args:
            types: Types of conversations to include (im, mpim)

        Returns:
            List of DM conversation objects
        """
        try:
            response = self.client.conversations_list(
                types=types,
                exclude_archived=False
            )
            return response.data.get('channels', [])
        except SlackApiError as e:
            logger.error(f"Failed to list DM conversations: {e.response['error']}")
            raise Exception(f"Failed to list DM conversations: {e.response['error']}")

    def find_dm_channel_with_user(self, user_id: str) -> str:
        """
        Find existing DM channel with a specific user without creating a new conversation

        Args:
            user_id: Slack user ID to find DM channel with

        Returns:
            Channel ID if found, None if no existing DM conversation
        """
        try:
            # Get all DM conversations
            dm_conversations = self.list_dm_conversations()

            for conversation in dm_conversations:
                # For DMs (type 'im'), check if the user is part of the conversation
                if conversation.get('is_im') and user_id in conversation.get('user', ''):
                    logger.info(f"Found existing DM channel {conversation['id']} with user {user_id}")
                    return conversation['id']

                # For multi-person DMs (type 'mpim'), check if user is in members
                if conversation.get('is_mpim'):
                    members = conversation.get('members', [])
                    if user_id in members:
                        logger.info(f"Found existing MPIM channel {conversation['id']} with user {user_id}")
                        return conversation['id']

            logger.info(f"No existing DM conversation found with user {user_id}")
            return None

        except Exception as e:
            logger.error(f"Error finding DM channel with user {user_id}: {str(e)}")
            return None

    @staticmethod
    def create_user_token_service(user_token: str):
        """
        Create SlackAPIService instance with user token for accessing real DM conversations
        """
        return SlackAPIService(user_token)

    def get_dm_history_with_user_token(self, channel: str, limit: int = 100, oldest: str = None,
                       latest: str = None, cursor: str = None) -> Dict[str, Any]:
        """
        Get direct message history using user token (can access real human conversations)
        """
        try:
            params = {
                'channel': channel,
                'limit': min(limit, 1000),
                'include_all_metadata': True
            }

            if oldest:
                params['oldest'] = oldest
            if latest:
                params['latest'] = latest
            if cursor:
                params['cursor'] = cursor

            response = self.client.conversations_history(**params)

            return {
                'messages': response.data.get('messages', []),
                'has_more': response.data.get('has_more', False),
                'response_metadata': response.data.get('response_metadata', {}),
                'channel': channel,
                'ok': response.data.get('ok', True),
                'token_type': 'user'  # Indicate this used user token
            }
        except SlackApiError as e:
            logger.error(f"Failed to get DM history with user token: {e.response['error']}")
            raise Exception(f"Failed to get DM history: {e.response['error']}")

    def get_dm_history(self, channel: str, limit: int = 100, oldest: str = None,
                       latest: str = None, cursor: str = None) -> Dict[str, Any]:
        """
        Get direct message history

        Args:
            channel: DM channel ID
            limit: Number of messages to retrieve (max 1000)
            oldest: Start of time range (timestamp)
            latest: End of time range (timestamp)
            cursor: Pagination cursor

        Returns:
            Dict containing messages and pagination info
        """
        try:
            params = {
                'channel': channel,
                'limit': min(limit, 1000),
                'include_all_metadata': True
            }

            if oldest:
                params['oldest'] = oldest
            if latest:
                params['latest'] = latest
            if cursor:
                params['cursor'] = cursor

            response = self.client.conversations_history(**params)

            return {
                'messages': response.data.get('messages', []),
                'has_more': response.data.get('has_more', False),
                'response_metadata': response.data.get('response_metadata', {}),
                'channel': channel,
                'ok': response.data.get('ok', True)
            }
        except SlackApiError as e:
            logger.error(f"Failed to get DM history: {e.response['error']}")
            raise Exception(f"Failed to get DM history: {e.response['error']}")

    def send_dm(self, user_id: str, text: str, **kwargs) -> Dict[str, Any]:
        """
        Send a direct message to a user

        Args:
            user_id: Slack user ID to send message to
            text: Message text
            **kwargs: Additional message parameters

        Returns:
            Dict containing message response
        """
        try:
            # First, open a DM conversation with the user
            dm_response = self.open_dm_conversation(user_id)
            channel_id = dm_response.get('channel', {}).get('id')

            if not channel_id:
                raise Exception("Failed to get DM channel ID")

            # Send the message to the DM channel
            response = self.client.chat_postMessage(
                channel=channel_id,
                text=text,
                **kwargs
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Failed to send DM: {e.response['error']}")
            raise Exception(f"Failed to send DM: {e.response['error']}")

    def list_workspace_users(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        List users in the workspace (for DM recipients)

        Args:
            limit: Maximum number of users to retrieve

        Returns:
            List of user objects
        """
        try:
            response = self.client.users_list(limit=limit)

            # Filter out bots and deleted users
            users = []
            for user in response.data.get('members', []):
                if not user.get('deleted', False) and not user.get('is_bot', False):
                    users.append({
                        'id': user.get('id'),
                        'name': user.get('name'),
                        'real_name': user.get('real_name'),
                        'display_name': user.get('profile', {}).get('display_name'),
                        'email': user.get('profile', {}).get('email'),
                        'image': user.get('profile', {}).get('image_48'),
                        'is_admin': user.get('is_admin', False),
                        'is_owner': user.get('is_owner', False)
                    })

            return users
        except SlackApiError as e:
            logger.error(f"Failed to list workspace users: {e.response['error']}")
            raise Exception(f"Failed to list workspace users: {e.response['error']}")

    def get_all_dm_messages(self, limit_per_dm: int = 20, oldest: str = None,
                           latest: str = None) -> Dict[str, Any]:
        """
        Get messages from all direct message conversations

        Args:
            limit_per_dm: Number of messages per DM conversation
            oldest: Start of time range (timestamp)
            latest: End of time range (timestamp)

        Returns:
            Dict with messages organized by DM conversation
        """
        results = {
            'conversations': {},
            'successful_conversations': [],
            'failed_conversations': [],
            'total_messages': 0
        }

        try:
            # Get all DM conversations
            dm_conversations = self.list_dm_conversations()

            for conversation in dm_conversations:
                channel_id = conversation.get('id')
                try:
                    dm_data = self.get_dm_history(
                        channel=channel_id,
                        limit=limit_per_dm,
                        oldest=oldest,
                        latest=latest
                    )

                    # Add conversation metadata
                    dm_data['conversation_info'] = {
                        'type': conversation.get('is_mpim') and 'mpim' or 'im',
                        'user': conversation.get('user'),
                        'created': conversation.get('created'),
                        'is_user_deleted': conversation.get('is_user_deleted', False)
                    }

                    results['conversations'][channel_id] = dm_data
                    results['successful_conversations'].append(channel_id)
                    results['total_messages'] += len(dm_data.get('messages', []))

                    logger.info(f"Retrieved {len(dm_data.get('messages', []))} messages from DM {channel_id}")

                except Exception as e:
                    error_msg = str(e)
                    results['failed_conversations'].append({
                        'conversation': channel_id,
                        'error': error_msg
                    })
                    logger.error(f"Failed to get messages from DM {channel_id}: {error_msg}")

            return results

        except Exception as e:
            logger.error(f"Failed to get messages from all DMs: {str(e)}")
            raise Exception(f"Failed to get messages from all DMs: {str(e)}")

    def bulk_join_channels(self) -> Dict[str, Any]:
        """
        Join all available public channels that the bot has access to
        """
        results = {
            'joined': [],
            'already_joined': [],
            'failed': [],
            'private_channels': []
        }

        try:
            # Get list of all channels
            channels = self.list_channels(types="public_channel")

            for channel in channels:
                channel_id = channel['id']
                channel_name = channel['name']

                try:
                    # Try to join each channel
                    self.join_channel(channel_id)
                    results['joined'].append({
                        'id': channel_id,
                        'name': channel_name
                    })
                    logger.info(f"Successfully joined channel #{channel_name}")

                except Exception as e:
                    error_message = str(e)
                    if 'already_in_channel' in error_message:
                        results['already_joined'].append({
                            'id': channel_id,
                            'name': channel_name
                        })
                    elif 'is_private' in error_message:
                        results['private_channels'].append({
                            'id': channel_id,
                            'name': channel_name
                        })
                    else:
                        results['failed'].append({
                            'id': channel_id,
                            'name': channel_name,
                            'error': error_message
                        })
                        logger.error(f"Failed to join channel #{channel_name}: {error_message}")

            return results

        except Exception as e:
            logger.error(f"Failed to get channel list for bulk join: {str(e)}")
            raise Exception(f"Failed to get channel list: {str(e)}")


class SlackDataService:
    """
    Service for managing Slack data in local database
    """
    
    @staticmethod
    def sync_channels(workspace: SlackWorkspace, token: str, max_retries: int = 3):
        """
        Sync channels from Slack API to local database with retry logic
        """
        import time

        last_exception = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Syncing channels for workspace {workspace.team_name} (attempt {attempt + 1}/{max_retries})")

                # Initialize Slack service
                slack_service = SlackAPIService(token)

                # Get channels from Slack API
                channels_data = slack_service.list_channels()
                logger.info(f"Retrieved {len(channels_data)} channels from Slack API")

                # Track sync statistics
                synced_count = 0
                updated_count = 0

                # Sync each channel to database
                for channel_data in channels_data:
                    channel, created = SlackChannel.objects.update_or_create(
                        workspace=workspace,
                        channel_id=channel_data['id'],
                        defaults={
                            'channel_name': channel_data.get('name'),
                            'channel_type': 'private_channel' if channel_data.get('is_private') else 'public_channel',
                            'is_private': channel_data.get('is_private', False),
                            'is_archived': channel_data.get('is_archived', False),
                        }
                    )

                    if created:
                        synced_count += 1
                        logger.debug(f"Created new channel: #{channel.channel_name} ({channel.channel_id})")
                    else:
                        updated_count += 1
                        logger.debug(f"Updated existing channel: #{channel.channel_name} ({channel.channel_id})")

                # Validate sync success
                total_channels = SlackChannel.objects.filter(workspace=workspace, is_archived=False).count()

                logger.info(f"Channel sync completed for {workspace.team_name}:")
                logger.info(f"  - {synced_count} new channels created")
                logger.info(f"  - {updated_count} existing channels updated")
                logger.info(f"  - {total_channels} total active channels in database")

                # Return success metrics
                return {
                    'success': True,
                    'channels_retrieved': len(channels_data),
                    'channels_created': synced_count,
                    'channels_updated': updated_count,
                    'total_active': total_channels,
                    'attempt': attempt + 1
                }

            except Exception as e:
                last_exception = e
                logger.warning(f"Channel sync attempt {attempt + 1} failed for {workspace.team_name}: {str(e)}")

                if attempt < max_retries - 1:
                    # Wait before retry (exponential backoff)
                    wait_time = (2 ** attempt) * 1.0  # 1s, 2s, 4s
                    logger.info(f"Retrying channel sync in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries} channel sync attempts failed for {workspace.team_name}")

        # If we get here, all retries failed
        error_msg = f"Failed to sync channels after {max_retries} attempts: {str(last_exception)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'last_exception': str(last_exception),
            'attempts': max_retries
        }
    
    @staticmethod
    def get_user_workspaces(user) -> List[SlackWorkspace]:
        """
        Get all workspaces connected by a user
        """
        slack_users = SlackUser.objects.filter(user=user, is_active=True)
        return [su.workspace for su in slack_users]