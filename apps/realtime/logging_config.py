import logging
import sys
from datetime import datetime
from django.conf import settings


class SlackRealTimeFormatter(logging.Formatter):
    """
    Custom formatter for Slack real-time messaging logs
    """

    def format(self, record):
        # Add timestamp
        record.timestamp = datetime.now().isoformat()

        # Add module info
        record.module_name = record.module
        record.function_name = record.funcName

        # Color coding for different log levels (for console)
        colors = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m', # Magenta
        }

        reset_color = '\033[0m'

        if hasattr(record, 'levelname'):
            color = colors.get(record.levelname, '')
            record.colored_levelname = f"{color}{record.levelname}{reset_color}"

        return super().format(record)


class SlackEventFilter(logging.Filter):
    """
    Filter for Slack event-specific logs
    """

    def filter(self, record):
        # Add slack-specific context if available
        if hasattr(record, 'slack_event_type'):
            record.msg = f"[{record.slack_event_type}] {record.msg}"

        if hasattr(record, 'team_id'):
            record.msg = f"[Team:{record.team_id}] {record.msg}"

        if hasattr(record, 'channel_id'):
            record.msg = f"[Channel:{record.channel_id}] {record.msg}"

        return True


def setup_slack_logging():
    """
    Set up comprehensive logging for Slack real-time messaging
    """

    # Create logger
    logger = logging.getLogger('slack_realtime')
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = SlackRealTimeFormatter(
        fmt='%(timestamp)s | %(colored_levelname)s | %(module_name)s.%(function_name)s:%(lineno)d | %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(SlackEventFilter())

    # File handler for persistent logs
    try:
        import os
        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.FileHandler(
            os.path.join(log_dir, 'slack_realtime.log'),
            encoding='utf-8'
        )
        file_formatter = SlackRealTimeFormatter(
            fmt='%(timestamp)s | %(levelname)s | %(module_name)s.%(function_name)s:%(lineno)d | %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(SlackEventFilter())

        logger.addHandler(file_handler)

    except Exception as e:
        print(f"Warning: Could not set up file logging: {e}")

    logger.addHandler(console_handler)

    # Also set up the main slack_api logger
    slack_api_logger = logging.getLogger('slack_api')
    if not slack_api_logger.handlers:
        slack_api_logger.addHandler(console_handler)
        if 'file_handler' in locals():
            slack_api_logger.addHandler(file_handler)
        slack_api_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    return logger


def log_slack_event(logger, event_type, team_id=None, channel_id=None, message=None, level=logging.INFO):
    """
    Log Slack events with structured context
    """
    extra = {
        'slack_event_type': event_type,
        'team_id': team_id,
        'channel_id': channel_id,
    }

    logger.log(level, message or f"Processing {event_type} event", extra=extra)


def log_performance_metric(logger, operation, duration_ms, event_type=None, team_id=None):
    """
    Log performance metrics for monitoring
    """
    extra = {
        'operation': operation,
        'duration_ms': duration_ms,
        'slack_event_type': event_type,
        'team_id': team_id,
    }

    if duration_ms > 1000:  # Log slow operations as warnings
        level = logging.WARNING
        message = f"SLOW {operation}: {duration_ms:.2f}ms"
    else:
        level = logging.DEBUG
        message = f"{operation}: {duration_ms:.2f}ms"

    logger.log(level, message, extra=extra)


def log_websocket_event(logger, event_type, user_id=None, connection_count=None, message=None):
    """
    Log WebSocket events with context
    """
    extra = {
        'websocket_event_type': event_type,
        'user_id': user_id,
        'connection_count': connection_count,
    }

    logger.info(message or f"WebSocket {event_type}", extra=extra)


# Initialize logging when module is imported
if not hasattr(setup_slack_logging, '_initialized'):
    setup_slack_logging._initialized = True
    setup_slack_logging()