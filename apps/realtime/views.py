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
    Verify that the request came from Slack by validating the signature
    """
    if not settings.REALTIME_SETTINGS.get('SLACK_WEBHOOK_VERIFICATION', True):
        return True

    try:
        # Get timestamp and signature from headers
        timestamp = request.META.get('HTTP_X_SLACK_REQUEST_TIMESTAMP')
        signature = request.META.get('HTTP_X_SLACK_SIGNATURE')

        if not timestamp or not signature:
            logger.warning("Missing timestamp or signature in Slack request")
            return False

        # Get request body
        body = request.body.decode('utf-8')

        # Create the signature string
        sig_basestring = f'v0:{timestamp}:{body}'

        # Create expected signature
        expected_signature = 'v0=' + hmac.new(
            signing_secret.encode('utf-8'),
            sig_basestring.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Compare signatures
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("Slack signature verification failed")
            return False

        # Check timestamp to prevent replay attacks (should be within 5 minutes)
        import time
        current_time = int(time.time())
        request_time = int(timestamp)

        if abs(current_time - request_time) > 300:  # 5 minutes
            logger.warning("Slack request timestamp too old")
            return False

        return True

    except Exception as e:
        logger.error(f"Error verifying Slack request: {str(e)}")
        return False


@method_decorator(csrf_exempt, name='dispatch')
class SlackEventsWebhookView(APIView):
    """
    Main webhook endpoint for Slack Events API
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request, client_identifier=None, *args, **kwargs):
        """Handle incoming Slack events"""
        try:
            # Parse JSON payload
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                logger.error("Invalid JSON in Slack webhook")
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
            from apps.core.models import SlackAppConfiguration
            app_config = None

            if client_identifier:
                try:
                    app_config = SlackAppConfiguration.objects.get(
                        client_identifier=client_identifier,
                        is_active=True
                    )
                except SlackAppConfiguration.DoesNotExist:
                    logger.error(f"No configuration found for client: {client_identifier}")
                    return Response({
                        'error': 'Invalid client configuration'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                # Use primary configuration
                app_config = SlackAppConfiguration.objects.filter(is_active=True).first()

            # Verify request signature if configuration is available
            if app_config and app_config.signing_secret:
                if not verify_slack_request(request, app_config.signing_secret):
                    return Response({
                        'error': 'Invalid request signature'
                    }, status=status.HTTP_401_UNAUTHORIZED)

            elif event_type == 'event_callback':
                # Actual event from Slack
                event = payload.get('event', {})
                team_id = payload.get('team_id')
                api_app_id = payload.get('api_app_id')

                logger.info(f"Received Slack event: {event.get('type')} from team {team_id}")

                # Process the event asynchronously
                from asgiref.sync import async_to_sync
                event_handler = SlackEventHandler(app_config)
                result = async_to_sync(event_handler.handle_event)(event, team_id, api_app_id)

                if result.get('success'):
                    return Response({'status': 'ok'}, status=status.HTTP_200_OK)
                else:
                    logger.error(f"Event processing failed: {result.get('error')}")
                    return Response({'status': 'error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            elif event_type == 'app_rate_limited':
                # Handle rate limiting
                logger.warning(f"App rate limited by Slack: {payload}")
                return Response({'status': 'rate_limited'}, status=status.HTTP_200_OK)

            else:
                logger.warning(f"Unknown Slack event type: {event_type}")
                return Response({'status': 'unknown_event'}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Slack webhook processing error: {str(e)}")
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