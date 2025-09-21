"""
Django management command to start Socket Mode client
Usage: python manage.py start_socket_mode
"""
import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.realtime.socket_mode_client import SlackSocketModeClient

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Start Slack Socket Mode client for real-time DM monitoring'

    def add_arguments(self, parser):
        parser.add_argument(
            '--app-token',
            type=str,
            help='Slack App-level token (xapp-1-...)',
        )
        parser.add_argument(
            '--bot-token',
            type=str,
            help='Slack Bot token (xoxb-...)',
        )

    def handle(self, *args, **options):
        """Start the Socket Mode client"""
        self.stdout.write("🚀 Starting Slack Socket Mode client...")

        # Get tokens from options or settings
        app_token = options.get('app_token') or getattr(settings, 'SLACK_APP_TOKEN', None)
        bot_token = options.get('bot_token') or getattr(settings, 'SLACK_BOT_TOKEN', None)

        if not app_token:
            self.stdout.write(
                self.style.ERROR("❌ Missing SLACK_APP_TOKEN. Please set in .env or pass --app-token")
            )
            return

        if not bot_token:
            self.stdout.write(
                self.style.ERROR("❌ Missing SLACK_BOT_TOKEN. Please set in .env or pass --bot-token")
            )
            return

        self.stdout.write(f"🔑 Using App Token: {app_token[:15]}...")
        self.stdout.write(f"🤖 Using Bot Token: {bot_token[:15]}...")

        try:
            # Start Socket Mode client
            client = SlackSocketModeClient(app_token, bot_token)

            self.stdout.write(
                self.style.SUCCESS("✅ Socket Mode client starting...")
            )
            self.stdout.write(
                self.style.WARNING("📱 This will monitor ALL direct messages and channel messages in real-time")
            )
            self.stdout.write(
                self.style.WARNING("⏹️  Press Ctrl+C to stop")
            )

            # Run the client
            asyncio.run(client.start())

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\n⏹️  Socket Mode client stopped by user")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error starting Socket Mode client: {e}")
            )
            logger.error(f"Socket Mode client error: {e}", exc_info=True)