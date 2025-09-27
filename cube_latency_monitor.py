#!/usr/bin/env python3
"""
Standalone Cube Latency Monitor

Pings all cubes (1-6 and 11-16) once per second and logs response times to a JSONL file.
Records timestamp, cube number, and ping time for each response.

Usage:
    python cube_latency_monitor.py [--broker BROKER] [--output OUTPUT] [--duration DURATION]
"""

import asyncio
import aiomqtt
import argparse
import json
import time
import uuid
from datetime import datetime
import sys
import signal


class CubeLatencyMonitor:
    def __init__(self, broker="192.168.8.247"):
        self.broker = broker
        self.cube_ids = [1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16]  # P0 and P1 cubes
        self.pending_pings = {}  # ping_id -> (cube_id, send_time)
        self.running = True
        self.output_file = None

    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.running = False

    async def monitor_cubes(self, output_file="cube_latency.jsonl", duration=None):
        """Monitor cube latency continuously"""
        self.output_file = output_file

        print(f"🔍 Starting continuous cube latency monitoring")
        print(f"📡 Broker: {self.broker}")
        print(f"🎯 Cubes: {self.cube_ids}")
        print(f"📝 Output: {output_file}")
        if duration:
            print(f"⏱️  Duration: {duration} seconds")
        print(f"🔄 Ping interval: 1 second")
        print()

        try:
            async with aiomqtt.Client(self.broker, timeout=10) as client:
                # Subscribe to all echo topics
                for cube_id in self.cube_ids:
                    echo_topic = f"cube/{cube_id}/echo"
                    await client.subscribe(echo_topic)

                print("📡 Subscribed to all cube echo topics")
                print("🚀 Starting monitoring loop...")
                print()

                # Start message listener task
                listen_task = asyncio.create_task(
                    self._listen_for_responses(client)
                )

                # Open output file for writing
                with open(output_file, 'a') as f:  # Append mode for continuous logging
                    start_time = time.time()
                    ping_count = 0

                    while self.running:
                        if duration and (time.time() - start_time) > duration:
                            break

                        ping_count += 1
                        current_time = time.time()

                        # Send ping to all cubes simultaneously
                        ping_tasks = []
                        for cube_id in self.cube_ids:
                            task = self._send_ping(client, cube_id, ping_count, current_time)
                            ping_tasks.append(task)

                        await asyncio.gather(*ping_tasks)

                        # Mark timeouts for pings that are too old (>5 seconds)
                        await self._mark_timeouts(f, current_time)

                        # Wait for next ping cycle (1 second)
                        await asyncio.sleep(1.0)

                    # Final timeout check
                    await self._mark_timeouts(f, time.time(), final=True)

                # Cancel listener task
                listen_task.cancel()
                try:
                    await listen_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            print(f"❌ Error during monitoring: {e}")
            raise

        print("\n✅ Monitoring completed")

    async def _send_ping(self, client, cube_id, ping_count, send_time):
        """Send ping to a specific cube"""
        ping_id = f"ping_{cube_id}_{ping_count}_{str(uuid.uuid4())[:8]}"

        # Store pending ping
        self.pending_pings[ping_id] = (cube_id, send_time)

        # Send ping
        ping_topic = f"cube/{cube_id}/ping"
        await client.publish(ping_topic, ping_id)

    async def _listen_for_responses(self, client):
        """Listen for ping echo responses"""
        try:
            async for message in client.messages:
                topic_parts = str(message.topic).split('/')
                if len(topic_parts) >= 3 and topic_parts[2] == 'echo':
                    await self._handle_ping_response(message)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"⚠️  Error in message listener: {e}")

    async def _handle_ping_response(self, message):
        """Handle a ping echo response"""
        try:
            topic_parts = str(message.topic).split('/')
            cube_id = int(topic_parts[1])
            receive_time = time.time()
            ping_id = message.payload.decode()

            if ping_id in self.pending_pings:
                stored_cube_id, send_time = self.pending_pings[ping_id]

                # Verify cube ID matches
                if cube_id == stored_cube_id:
                    response_time_ms = (receive_time - send_time) * 1000

                    result = {
                        'timestamp': datetime.fromtimestamp(receive_time).isoformat(),
                        'cube_id': cube_id,
                        'ping_time_ms': round(response_time_ms, 1)
                    }

                    # Write immediately to file
                    await self._write_result(result)

                    # Remove from pending
                    del self.pending_pings[ping_id]

                    print(f"📊 Cube {cube_id:2d}: {response_time_ms:6.1f}ms")
                else:
                    print(f"⚠️  Cube ID mismatch: expected {stored_cube_id}, got {cube_id}")
            else:
                # Could be a late response or from another source
                pass

        except Exception as e:
            print(f"⚠️  Error handling ping response: {e}")

    async def _write_result(self, result):
        """Write a single result to the output file"""
        if self.output_file:
            try:
                with open(self.output_file, 'a') as f:
                    f.write(json.dumps(result) + '\n')
                    f.flush()  # Ensure immediate write
            except Exception as e:
                print(f"⚠️  Error writing result: {e}")

    async def _mark_timeouts(self, file_handle, current_time, final=False):
        """Mark old pending pings as timeouts"""
        timeout_threshold = 5.0 if not final else 0.0  # 5 seconds for timeout, 0 for final

        timed_out_pings = []
        for ping_id, (cube_id, send_time) in self.pending_pings.items():
            if (current_time - send_time) > timeout_threshold:
                timed_out_pings.append(ping_id)

        for ping_id in timed_out_pings:
            cube_id, send_time = self.pending_pings[ping_id]

            timeout_result = {
                'timestamp': datetime.fromtimestamp(current_time).isoformat(),
                'cube_id': cube_id,
                'ping_time_ms': None
            }

            # Write timeout to file
            file_handle.write(json.dumps(timeout_result) + '\n')
            file_handle.flush()

            # Remove from pending
            del self.pending_pings[ping_id]

            if not final:  # Don't spam during final cleanup
                print(f"⏱️  Cube {cube_id:2d}: TIMEOUT")


def main():
    parser = argparse.ArgumentParser(description="Monitor cube latency continuously")
    parser.add_argument("--broker", default="192.168.8.247", help="MQTT broker address")
    parser.add_argument("--output", default="cube_latency.jsonl", help="Output JSONL file")
    parser.add_argument("--duration", type=int, help="Duration in seconds (default: run indefinitely)")

    args = parser.parse_args()

    monitor = CubeLatencyMonitor(broker=args.broker)

    # Set up signal handlers for clean shutdown
    def signal_handler(sig, frame):
        print(f"\n🛑 Received signal {sig}, stopping monitoring...")
        monitor.stop_monitoring()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(monitor.monitor_cubes(
            output_file=args.output,
            duration=args.duration
        ))
    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()