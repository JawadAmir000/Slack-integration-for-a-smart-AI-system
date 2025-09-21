import logging
import traceback
import asyncio
from functools import wraps
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from .logging_config import log_slack_event, log_performance_metric

logger = logging.getLogger('slack_realtime')


class SlackEventError(Exception):
    """Custom exception for Slack event processing errors"""

    def __init__(self, message, event_type=None, team_id=None, error_code=None):
        super().__init__(message)
        self.event_type = event_type
        self.team_id = team_id
        self.error_code = error_code


class SlackWebSocketError(Exception):
    """Custom exception for WebSocket-related errors"""

    def __init__(self, message, user_id=None, connection_id=None, error_code=None):
        super().__init__(message)
        self.user_id = user_id
        self.connection_id = connection_id
        self.error_code = error_code


def with_error_handling(event_type=None, max_retries=3, retry_delay=1.0):
    """
    Decorator for comprehensive error handling with retry logic
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = asyncio.get_event_loop().time()
            attempts = 0
            last_error = None

            while attempts < max_retries:
                try:
                    result = await func(*args, **kwargs)

                    # Log successful execution time
                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    log_performance_metric(
                        logger, func.__name__, duration_ms, event_type,
                        kwargs.get('team_id')
                    )

                    return result

                except SlackEventError as e:
                    last_error = e
                    log_slack_event(
                        logger, e.event_type or event_type, e.team_id,
                        message=f"SlackEventError in {func.__name__}: {str(e)}",
                        level=logging.ERROR
                    )

                    # Don't retry certain error types
                    if e.error_code in ['VALIDATION_ERROR', 'AUTH_ERROR']:
                        break

                except SlackWebSocketError as e:
                    last_error = e
                    logger.error(f"WebSocket error in {func.__name__}: {str(e)}")
                    break  # Don't retry WebSocket errors

                except Exception as e:
                    last_error = e
                    logger.error(
                        f"Unexpected error in {func.__name__}: {str(e)}\n"
                        f"Traceback: {traceback.format_exc()}"
                    )

                attempts += 1
                if attempts < max_retries:
                    await asyncio.sleep(retry_delay * attempts)  # Exponential backoff

            # All retries failed
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.error(
                f"Function {func.__name__} failed after {attempts} attempts "
                f"({duration_ms:.2f}ms total). Last error: {str(last_error)}"
            )

            return {
                'success': False,
                'error': str(last_error),
                'attempts': attempts,
                'duration_ms': duration_ms
            }

        return wrapper
    return decorator


class ErrorTracker:
    """
    Track and analyze error patterns for monitoring
    """

    @staticmethod
    def record_error(error_type, context=None, team_id=None):
        """Record an error occurrence for pattern analysis"""
        try:
            now = datetime.now()
            cache_key = f"slack_error:{error_type}:{now.strftime('%Y%m%d%H')}"

            # Increment hourly error count
            error_count = cache.get(cache_key, 0) + 1
            cache.set(cache_key, error_count, timeout=3600)  # 1 hour

            # Log error pattern if threshold exceeded
            if error_count > 10:  # Configurable threshold
                logger.warning(
                    f"High error rate detected: {error_type} "
                    f"occurred {error_count} times in the past hour"
                )

                # Alert if very high error rate
                if error_count > 50:
                    ErrorTracker.send_error_alert(error_type, error_count, team_id)

        except Exception as e:
            logger.error(f"Error tracking failed: {str(e)}")

    @staticmethod
    def send_error_alert(error_type, count, team_id=None):
        """Send error alerts for critical issues"""
        try:
            # In a real implementation, this could send alerts via:
            # - Email
            # - Slack notification
            # - External monitoring service

            logger.critical(
                f"CRITICAL ERROR RATE: {error_type} "
                f"occurred {count} times in the past hour "
                f"(Team: {team_id})"
            )

            # You could integrate with monitoring services here
            # e.g., Sentry, Datadog, PagerDuty

        except Exception as e:
            logger.error(f"Failed to send error alert: {str(e)}")

    @staticmethod
    def get_error_stats(hours=24):
        """Get error statistics for monitoring dashboard"""
        try:
            stats = {}
            now = datetime.now()

            for hour_offset in range(hours):
                hour = now - timedelta(hours=hour_offset)
                cache_pattern = f"slack_error:*:{hour.strftime('%Y%m%d%H')}"

                # This is a simplified version - in production, you'd want
                # a more efficient way to query error patterns

            return stats

        except Exception as e:
            logger.error(f"Failed to get error stats: {str(e)}")
            return {}


class PerformanceMonitor:
    """
    Monitor performance metrics for optimization
    """

    @staticmethod
    def track_websocket_connection(user_id=None, action='connect'):
        """Track WebSocket connection metrics"""
        try:
            cache_key = f"ws_connections:{datetime.now().strftime('%Y%m%d%H%M')}"
            connections = cache.get(cache_key, 0)

            if action == 'connect':
                connections += 1
            elif action == 'disconnect':
                connections = max(0, connections - 1)

            cache.set(cache_key, connections, timeout=3600)

            # Log connection stats
            if connections % 10 == 0:  # Log every 10 connections
                logger.info(f"WebSocket connections: {connections}")

        except Exception as e:
            logger.error(f"Connection tracking failed: {str(e)}")

    @staticmethod
    def track_message_latency(event_timestamp, processing_start):
        """Track message processing latency"""
        try:
            # Calculate latency from Slack event to processing start
            if event_timestamp:
                latency_ms = (processing_start - float(event_timestamp)) * 1000

                # Log slow messages
                if latency_ms > 5000:  # 5 seconds
                    logger.warning(f"High message latency: {latency_ms:.2f}ms")

                # Store for analytics
                cache_key = f"msg_latency:{datetime.now().strftime('%Y%m%d%H')}"
                latencies = cache.get(cache_key, [])
                latencies.append(latency_ms)

                # Keep only last 100 latencies per hour
                if len(latencies) > 100:
                    latencies = latencies[-100:]

                cache.set(cache_key, latencies, timeout=3600)

        except Exception as e:
            logger.error(f"Latency tracking failed: {str(e)}")


def handle_critical_error(error, context=None):
    """
    Handle critical errors that require immediate attention
    """
    try:
        error_msg = str(error)

        # Log critical error
        logger.critical(
            f"CRITICAL ERROR: {error_msg}\n"
            f"Context: {context}\n"
            f"Traceback: {traceback.format_exc()}"
        )

        # Record for pattern analysis
        ErrorTracker.record_error('CRITICAL', context)

        # In production, you might want to:
        # - Send immediate alerts
        # - Trigger emergency procedures
        # - Gracefully degrade service

    except Exception as e:
        # Last resort logging
        print(f"Critical error handler failed: {str(e)}")


def safe_json_serialize(data):
    """
    Safely serialize data to JSON, handling problematic types
    """
    import json
    from datetime import datetime, date

    def json_serializer(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return str(obj)
        else:
            return str(obj)

    try:
        return json.dumps(data, default=json_serializer, ensure_ascii=False)
    except Exception as e:
        logger.error(f"JSON serialization failed: {str(e)}")
        return json.dumps({'error': 'Serialization failed', 'original_error': str(e)})