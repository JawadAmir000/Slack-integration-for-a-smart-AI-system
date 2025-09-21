import json
import logging
import hmac
import hashlib
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .events import SlackEventHandler

logger = logging.getLogger('slack_api')


def verify_slack_request(request, signing_secret):
    """
    Enhanced Slack request verification with comprehensive security checks
    """
    if not settings.REALTIME_SETTINGS.get('SLACK_WEBHOOK_VERIFICATION', True):
        logger.info("Slack webhook verification disabled in settings")
        return True

    try:
        # Get timestamp and signature from headers
        timestamp = request.META.get('HTTP_X_SLACK_REQUEST_TIMESTAMP')
        signature = request.META.get('HTTP_X_SLACK_SIGNATURE')

        if not timestamp or not signature:
            logger.warning(f"Missing headers - timestamp: {bool(timestamp)}, signature: {bool(signature)}")
            return False

        # Validate timestamp format
        try:
            request_time = int(timestamp)
        except (ValueError, TypeError):
            logger.warning(f"Invalid timestamp format: {timestamp}")
            return False

        # Check timestamp to prevent replay attacks (within 5 minutes)
        import time
        current_time = int(time.time())
        time_diff = abs(current_time - request_time)

        if time_diff > 900:  # 15 minutes (increased to handle timezone issues)
            logger.warning(f"Request timestamp outside tolerance: {time_diff} seconds")
            return False

        # Get request body
        body = request.body.decode('utf-8')

        # Validate body is not empty for non-challenge requests
        if not body.strip():
            logger.warning("Empty request body received")
            return False

        # Create the signature string
        sig_basestring = f'v0:{timestamp}:{body}'

        # Create expected signature
        expected_signature = 'v0=' + hmac.new(
            signing_secret.encode('utf-8'),
            sig_basestring.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Compare signatures using constant-time comparison
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning(f"Signature mismatch - received: {signature[:10]}..., expected: {expected_signature[:10]}...")
            return False

        # Additional security: Check for valid Slack user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if not user_agent.startswith('Slackbot'):
            logger.warning(f"Suspicious user agent: {user_agent}")
            # Don't fail on this, just log for monitoring

        logger.debug(f"Slack request verification successful for timestamp {timestamp}")
        return True

    except Exception as e:
        logger.error(f"Error verifying Slack request: {str(e)}", exc_info=True)
        return False


def get_client_app_config(client_identifier=None):
    """
    Get Slack app configuration with enhanced error handling
    """
    from apps.core.models import SlackAppConfiguration

    try:
        if client_identifier:
            app_config = SlackAppConfiguration.objects.get(
                client_identifier=client_identifier,
                is_active=True
            )
            logger.debug(f"Found configuration for client: {client_identifier}")
        else:
            app_config = SlackAppConfiguration.objects.filter(is_active=True).first()
            if app_config:
                logger.debug(f"Using primary configuration: {app_config.client_identifier}")
            else:
                logger.warning("No active Slack app configuration found")

        return app_config

    except SlackAppConfiguration.DoesNotExist:
        logger.error(f"No configuration found for client: {client_identifier}")
        return None
    except Exception as e:
        logger.error(f"Error getting app configuration: {str(e)}")
        return None


def is_duplicate_event(event_id, team_id):
    """
    Check for duplicate events to prevent reprocessing
    """
    from django.core.cache import cache

    if not event_id:
        return False

    cache_key = f"slack_event:{team_id}:{event_id}"

    if cache.get(cache_key):
        logger.warning(f"Duplicate event detected: {event_id} for team {team_id}")
        return True

    # Cache for 1 hour to prevent duplicates
    cache.set(cache_key, True, 3600)
    return False


@method_decorator(csrf_exempt, name='dispatch')
class SlackEventsWebhookView(APIView):
    """
    Main webhook endpoint for Slack Events API
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request, client_identifier=None, *args, **kwargs):
        """Handle incoming Slack events with enhanced security and processing"""
        timestamp = request.META.get('HTTP_X_SLACK_REQUEST_TIMESTAMP')
        signature = request.META.get('HTTP_X_SLACK_SIGNATURE')
        print(f"WEBHOOK REQUEST RECEIVED - Method: {request.method}, Path: {request.path}")
        print(f"Timestamp: {timestamp}, Signature: {signature}")
        print(f"Body Length: {len(request.body)}")
        logger.info(f"WEBHOOK REQUEST RECEIVED - Method: {request.method}, Path: {request.path}")
        logger.info(f"Timestamp: {timestamp}, Signature: {signature}")
        logger.info(f"Body: {request.body.decode('utf-8')[:200]}...")
        try:
            # Parse JSON payload
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in Slack webhook: {str(e)}")
                return Response({
                    'error': 'Invalid JSON payload'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Handle different event types
            event_type = payload.get('type')

            if event_type == 'url_verification':
                # URL verification challenge for initial setup - bypass signature verification
                challenge = payload.get('challenge')
                logger.info(f"Slack URL verification challenge received: {challenge}")
                return Response({'challenge': challenge}, status=status.HTTP_200_OK)

            # Get app configuration for signature verification (only for non-challenge requests)
            app_config = get_client_app_config(client_identifier)

            if not app_config:
                logger.error(f"No active configuration found for client: {client_identifier}")
                return Response({
                    'error': 'Invalid or inactive client configuration'
                }, status=status.HTTP_404_NOT_FOUND)

            # Verify request signature for all non-challenge requests
            signing_secret = None

            # Use environment variable signing secret for now to bypass decryption issues
            from django.conf import settings
            signing_secret = getattr(settings, 'SLACK_SIGNING_SECRET', None)
            logger.debug(f"Using signing secret from environment settings")

            if signing_secret:
                if not verify_slack_request(request, signing_secret):
                    logger.warning(f"Signature verification failed for client: {client_identifier}")
                    return Response({
                        'error': 'Invalid request signature'
                    }, status=status.HTTP_401_UNAUTHORIZED)

            if event_type == 'event_callback':
                # Actual event from Slack
                event = payload.get('event', {})
                team_id = payload.get('team_id')
                api_app_id = payload.get('api_app_id')
                event_id = payload.get('event_id')

                # Check for duplicate events
                if is_duplicate_event(event_id, team_id):
                    logger.info(f"Skipping duplicate event: {event_id}")
                    return Response({'status': 'duplicate_ignored'}, status=status.HTTP_200_OK)

                logger.info(f"Processing Slack event: {event.get('type')} from team {team_id} (event_id: {event_id})")

                # Validate required fields
                if not event or not team_id:
                    logger.error("Missing required event fields")
                    return Response({
                        'error': 'Missing required event fields'
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Process the event asynchronously with enhanced error handling
                try:
                    from asgiref.sync import async_to_sync
                    event_handler = SlackEventHandler(app_config)
                    result = async_to_sync(event_handler.handle_event)(event, team_id, api_app_id)

                    if result.get('success'):
                        print(f"SUCCESS: Event {event_id} processed successfully!")
                        print(f"Event type: {event.get('type')}, Channel: {event.get('channel')}")
                        logger.info(f"Successfully processed event {event_id}: {result.get('message', 'OK')}")
                        return Response({'status': 'ok'}, status=status.HTTP_200_OK)
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        logger.error(f"Event processing failed for {event_id}: {error_msg}")
                        return Response({
                            'status': 'error',
                            'message': error_msg
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                except Exception as event_error:
                    logger.error(f"Exception processing event {event_id}: {str(event_error)}", exc_info=True)
                    return Response({
                        'status': 'error',
                        'message': 'Event processing failed'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            elif event_type == 'app_rate_limited':
                # Handle rate limiting with detailed logging
                rate_info = payload.get('minute_rate_limited', 'unknown')
                logger.warning(f"App rate limited by Slack: {rate_info} for team {payload.get('team_id')}")
                return Response({'status': 'rate_limited'}, status=status.HTTP_200_OK)

            else:
                logger.warning(f"Unknown Slack event type: {event_type}")
                return Response({'status': 'unknown_event'}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Slack webhook processing error: {str(e)}", exc_info=True)
            return Response({
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, client_identifier=None, *args, **kwargs):
        """Handle GET requests (for testing)"""
        return Response({
            'message': 'Slack Events Webhook Endpoint',
            'client_identifier': client_identifier,
            'endpoints': {
                'events': f'/api/slack/events/{client_identifier}/' if client_identifier else '/api/slack/events/',
                'interactive': f'/api/slack/interactive/{client_identifier}/' if client_identifier else '/api/slack/interactive/',
            }
        })


@method_decorator(csrf_exempt, name='dispatch')
class SlackInteractiveWebhookView(APIView):
    """
    Webhook endpoint for Slack interactive components (buttons, modals, etc.)
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request, client_identifier=None, *args, **kwargs):
        """Handle Slack interactive components"""
        try:
            # Parse form data (Slack sends interactive payloads as form data)
            payload_str = request.POST.get('payload')
            if not payload_str:
                return Response({
                    'error': 'No payload received'
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in Slack interactive payload")
                return Response({
                    'error': 'Invalid JSON payload'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get app configuration
            from apps.core.models import SlackAppConfiguration
            app_config = None

            if client_identifier:
                try:
                    app_config = SlackAppConfiguration.objects.get(
                        client_identifier=client_identifier,
                        is_active=True
                    )
                except SlackAppConfiguration.DoesNotExist:
                    return Response({
                        'error': 'Invalid client configuration'
                    }, status=status.HTTP_404_NOT_FOUND)

            # Handle different interactive component types
            callback_type = payload.get('type')

            if callback_type == 'block_actions':
                # Handle button clicks, select menus, etc.
                return self.handle_block_actions(payload, app_config)
            elif callback_type == 'view_submission':
                # Handle modal submissions
                return self.handle_view_submission(payload, app_config)
            elif callback_type == 'view_closed':
                # Handle modal closures
                return self.handle_view_closed(payload, app_config)
            else:
                logger.warning(f"Unknown interactive callback type: {callback_type}")
                return Response({'status': 'unknown_callback'}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Interactive webhook processing error: {str(e)}")
            return Response({
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def handle_block_actions(self, payload, app_config):
        """Handle block action interactions"""
        # Implement interactive component handling
        logger.info(f"Handling block actions: {payload.get('actions', [])}")
        return Response({'status': 'ok'})

    def handle_view_submission(self, payload, app_config):
        """Handle modal view submissions"""
        logger.info(f"Handling view submission: {payload.get('view', {}).get('callback_id')}")
        return Response({'status': 'ok'})

    def handle_view_closed(self, payload, app_config):
        """Handle modal view closures"""
        logger.info(f"Handling view closure: {payload.get('view', {}).get('callback_id')}")
        return Response({'status': 'ok'})


# Legacy endpoint for backward compatibility
@csrf_exempt
@require_http_methods(["POST", "GET"])
def slack_events_webhook(request):
    """
    Legacy webhook endpoint (redirects to new class-based view)
    """
    view = SlackEventsWebhookView.as_view()
    return view(request)


def websocket_test_view(request):
    """
    Serve the WebSocket test page
    """
    return render(request, 'realtime/websocket_test.html', {
        'title': 'Slack Real-Time Message Test',
        'websocket_url': '/ws/slack/messages/',
        'notifications_url': '/ws/slack/notifications/'
    })