#!/usr/bin/env python
"""
Simple ASGI server starter for development with proper WebSocket support
"""
import os
import sys
import django
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'slack_integration.settings')

    # Set up Django
    django.setup()

    # Import after Django is set up
    import uvicorn
    from slack_integration.asgi import application

    print("Starting ASGI server with WebSocket support...")
    print("Server will be available at: http://0.0.0.0:8000")
    print("WebSocket endpoints:")
    print("  - ws://0.0.0.0:8000/ws/slack/messages/")
    print("  - ws://0.0.0.0:8000/ws/slack/notifications/")
    print()

    # Start uvicorn server
    uvicorn.run(
        "slack_integration.asgi:application",
        host="0.0.0.0",
        port=8000,
        reload=True,
        access_log=True,
        log_level="info"
    )