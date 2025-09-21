import asyncio
import json
import time
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from channels.layers import get_channel_layer
from apps.realtime.events import SlackEventHandler
from apps.realtime.error_handling import PerformanceMonitor


class Command(BaseCommand):
    help = 'Test real-time Slack message delivery and WebSocket broadcasting'

    def add_arguments(self, parser):
        parser.add_argument(
            '--message-type',
            type=str,
            default='channel_message',
            choices=['channel_message', 'dm', 'reaction', 'typing', 'notification'],
            help='Type of test message to send'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=1,
            help='Number of test messages to send'
        )
        parser.add_argument(
            '--interval',
            type=float,
            default=1.0,
            help='Interval between messages (seconds)'
        )
        parser.add_argument(
            '--channel-id',
            type=str,
            default='C1234567890',
            help='Channel ID for test messages'
        )
        parser.add_argument(
            '--team-id',
            type=str,
            default='T1234567890',
            help='Team ID for test messages'
        )
        parser.add_argument(
            '--user-id',
            type=str,
            default='U1234567890',
            help='User ID for test messages'
        )
        parser.add_argument(
            '--stress-test',
            action='store_true',
            help='Run stress test with multiple concurrent messages'
        )
        parser.add_argument(
            '--validate-delivery',
            action='store_true',
            help='Validate message delivery timing'
        )

    def handle(self, *args, **options):
        """Execute the test command"""
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting real-time delivery test: {options['message_type']} "
                f"({options['count']} messages)"
            )
        )

        # Run async test
        asyncio.run(self.run_tests(options))

    async def run_tests(self, options):
        """Run the async test suite"""
        if options['stress_test']:
            await self.run_stress_test(options)
        elif options['validate_delivery']:
            await self.run_delivery_validation_test(options)
        else:
            await self.run_basic_test(options)

    async def run_basic_test(self, options):
        """Run basic message delivery test"""
        channel_layer = get_channel_layer()

        for i in range(options['count']):
            start_time = time.time()

            # Create test message
            test_message = self.create_test_message(options, i)

            # Send via WebSocket channel layer
            await self.send_test_message(channel_layer, test_message, options)

            # Calculate and log timing
            processing_time = (time.time() - start_time) * 1000

            self.stdout.write(
                f"Message {i+1}/{options['count']} sent in {processing_time:.2f}ms"
            )

            if i < options['count'] - 1:
                await asyncio.sleep(options['interval'])

        self.stdout.write(
            self.style.SUCCESS(f"✅ Sent {options['count']} test messages")
        )

    async def run_stress_test(self, options):
        """Run stress test with concurrent messages"""
        self.stdout.write(
            self.style.WARNING("🔥 Running stress test with concurrent messages")
        )

        channel_layer = get_channel_layer()
        start_time = time.time()

        # Create tasks for concurrent message sending
        tasks = []
        for i in range(options['count']):
            test_message = self.create_test_message(options, i)
            task = self.send_test_message(channel_layer, test_message, options)
            tasks.append(task)

        # Send all messages concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = (time.time() - start_time) * 1000
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        error_count = len(results) - success_count

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Stress test completed in {total_time:.2f}ms\n"
                f"   Success: {success_count}, Errors: {error_count}\n"
                f"   Throughput: {success_count / (total_time / 1000):.2f} msg/sec"
            )
        )

    async def run_delivery_validation_test(self, options):
        """Test and validate message delivery timing"""
        self.stdout.write(
            self.style.WARNING("⏱️  Running delivery validation test")
        )

        # Test different message types and measure latency
        test_cases = [
            {'type': 'channel_message', 'expected_latency_ms': 100},
            {'type': 'dm', 'expected_latency_ms': 50},
            {'type': 'reaction', 'expected_latency_ms': 50},
            {'type': 'typing', 'expected_latency_ms': 30},
        ]

        results = {}

        for test_case in test_cases:
            latencies = []

            for i in range(5):  # Test each type 5 times
                start_time = time.time()

                # Simulate event processing
                event_handler = SlackEventHandler()
                test_event = self.create_test_event(test_case['type'], options)

                result = await event_handler.handle_event(
                    test_event, options['team_id'], 'test_app_id'
                )

                latency_ms = (time.time() - start_time) * 1000
                latencies.append(latency_ms)

                # Small delay between tests
                await asyncio.sleep(0.1)

            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)

            results[test_case['type']] = {
                'avg_latency': avg_latency,
                'max_latency': max_latency,
                'expected': test_case['expected_latency_ms'],
                'passed': avg_latency <= test_case['expected_latency_ms']
            }

            status = "✅ PASS" if results[test_case['type']]['passed'] else "❌ FAIL"
            self.stdout.write(
                f"{status} {test_case['type']}: {avg_latency:.2f}ms avg "
                f"(max: {max_latency:.2f}ms, expected: <{test_case['expected_latency_ms']}ms)"
            )

        # Summary
        passed = sum(1 for r in results.values() if r['passed'])
        total = len(results)

        self.stdout.write(
            self.style.SUCCESS(f"\n📊 Validation Results: {passed}/{total} tests passed")
        )

    def create_test_message(self, options, index):
        """Create a test message based on type"""
        timestamp = datetime.now().isoformat()

        base_message = {
            'id': f'test_msg_{index}_{int(time.time())}',
            'channel_id': options['channel_id'],
            'user_id': options['user_id'],
            'workspace_id': options['team_id'],
            'timestamp': timestamp,
            'delivery_time': timestamp,
            'test_message': True,
            'test_index': index
        }

        if options['message_type'] == 'channel_message':
            return {
                **base_message,
                'channel_name': 'test-channel',
                'text': f'Test message #{index + 1} - {timestamp}',
                'event_type': 'message',
                'is_dm': False
            }

        elif options['message_type'] == 'dm':
            return {
                **base_message,
                'text': f'Test DM #{index + 1} - {timestamp}',
                'event_type': 'message',
                'is_dm': True
            }

        elif options['message_type'] == 'reaction':
            return {
                **base_message,
                'reaction': '👍',
                'event_type': 'reaction_added',
                'item': {
                    'type': 'message',
                    'channel': options['channel_id'],
                    'ts': str(time.time())
                }
            }

        elif options['message_type'] == 'typing':
            return {
                **base_message,
                'event_type': 'user_typing'
            }

        elif options['message_type'] == 'notification':
            return {
                **base_message,
                'notification_type': 'test',
                'message': f'Test notification #{index + 1}',
                'event_type': 'test_notification'
            }

        return base_message

    def create_test_event(self, event_type, options):
        """Create a test Slack event"""
        base_event = {
            'type': 'message' if event_type in ['channel_message', 'dm'] else event_type,
            'channel': options['channel_id'],
            'user': options['user_id'],
            'ts': str(time.time())
        }

        if event_type == 'channel_message':
            base_event.update({
                'text': 'Test channel message',
                'subtype': None
            })
        elif event_type == 'dm':
            base_event.update({
                'text': 'Test DM',
                'subtype': None
            })
        elif event_type == 'reaction':
            base_event.update({
                'type': 'reaction_added',
                'reaction': 'thumbsup',
                'item': {'type': 'message', 'channel': options['channel_id'], 'ts': str(time.time())}
            })
        elif event_type == 'typing':
            base_event.update({
                'type': 'user_typing'
            })

        return base_event

    async def send_test_message(self, channel_layer, message, options):
        """Send test message via WebSocket"""
        try:
            message_type = options['message_type']

            if message_type in ['channel_message', 'dm']:
                group_name = "slack_messages_anonymous"
                event_type = 'slack_channel_message' if message_type == 'channel_message' else 'slack_dm'
            elif message_type == 'reaction':
                group_name = "slack_notifications_anonymous"
                event_type = 'slack_reaction'
            elif message_type == 'typing':
                group_name = f"channel_{options['channel_id']}_anonymous"
                event_type = 'typing_indicator'
            else:
                group_name = "slack_notifications_anonymous"
                event_type = 'slack_notification'

            await channel_layer.group_send(group_name, {
                'type': event_type,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            self.stderr.write(f"Error sending test message: {str(e)}")
            raise

    def test_websocket_connection(self):
        """Test WebSocket connection functionality"""
        self.stdout.write("Testing WebSocket connection...")

        # This would ideally connect to the WebSocket and verify connectivity
        # For now, we'll just check if the channel layer is available

        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                self.stdout.write(
                    self.style.SUCCESS("✅ Channel layer is available")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("❌ Channel layer not configured")
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Channel layer error: {str(e)}")
            )