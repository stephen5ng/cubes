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
import socket
import subprocess
import re


class CubeLatencyMonitor:
    def __init__(self, broker="192.168.8.247"):
        self.broker = broker
        self.cube_ids = [1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16]  # P0 and P1 cubes
        self.pending_pings = {}  # ping_id -> (cube_id, send_time)
        self.pending_udp_pings = {}  # cube_id -> send_time
        self.pending_rssi_requests = {}  # cube_id -> send_time
        self.pending_timing_requests = {}  # cube_id -> send_time
        self.pending_temp_requests = {}  # cube_id -> send_time
        self.pending_icmp_pings = {}  # cube_id -> send_time
        self.running = True
        self.output_file = None
        self.udp_socket = None

    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.running = False
        if self.udp_socket:
            self.udp_socket.close()

    def setup_udp(self):
        """Setup UDP socket for cube pings"""
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.settimeout(0.1)  # 100ms timeout for non-blocking operation

    def get_cube_ip(self, cube_id):
        """Get IP address for a cube based on cube ID"""
        return f"192.168.8.{cube_id + 20}"  # 1-6 -> .21-.26, 11-16 -> .31-.36

    async def send_udp_ping(self, cube_id, send_time):
        """Send UDP ping to a specific cube"""
        if not self.udp_socket:
            return

        cube_ip = self.get_cube_ip(cube_id)
        self.pending_udp_pings[cube_id] = send_time

        try:
            self.udp_socket.sendto(b"ping", (cube_ip, 54321))
        except Exception as e:
            # Remove from pending if send failed
            self.pending_udp_pings.pop(cube_id, None)
            print(f"⚠️  UDP ping send failed to cube {cube_id}: {e}")

    async def send_rssi_request(self, cube_id, send_time):
        """Send RSSI request to a specific cube"""
        if not self.udp_socket:
            return

        cube_ip = self.get_cube_ip(cube_id)
        self.pending_rssi_requests[cube_id] = send_time

        try:
            self.udp_socket.sendto(b"rssi", (cube_ip, 54321))
        except Exception as e:
            # Remove from pending if send failed
            self.pending_rssi_requests.pop(cube_id, None)
            print(f"⚠️  UDP RSSI send failed to cube {cube_id}: {e}")

    async def send_timing_request(self, cube_id, send_time):
        """Send timing request to a specific cube"""
        if not self.udp_socket:
            return

        cube_ip = self.get_cube_ip(cube_id)
        self.pending_timing_requests[cube_id] = send_time

        try:
            self.udp_socket.sendto(b"timing", (cube_ip, 54321))
        except Exception as e:
            # Remove from pending if send failed
            self.pending_timing_requests.pop(cube_id, None)
            print(f"⚠️  UDP timing send failed to cube {cube_id}: {e}")

    async def send_temp_request(self, cube_id, send_time):
        """Send temperature request to a specific cube"""
        if not self.udp_socket:
            return

        cube_ip = self.get_cube_ip(cube_id)
        self.pending_temp_requests[cube_id] = send_time

        try:
            self.udp_socket.sendto(b"temp", (cube_ip, 54321))
        except Exception as e:
            # Remove from pending if send failed
            self.pending_temp_requests.pop(cube_id, None)
            print(f"⚠️  UDP temp send failed to cube {cube_id}: {e}")

    async def send_icmp_ping(self, cube_id, send_time):
        """Send ICMP ping to a specific cube"""
        cube_ip = self.get_cube_ip(cube_id)
        self.pending_icmp_pings[cube_id] = send_time

        # Run ping command asynchronously
        asyncio.create_task(self._execute_icmp_ping(cube_id, cube_ip, send_time))

    async def _execute_icmp_ping(self, cube_id, cube_ip, send_time):
        """Execute the actual ICMP ping command"""
        try:
            # Use ping command with 1 packet and 1 second timeout
            # -c 1: send 1 packet, -W 1000: timeout in ms (Linux/macOS compatible)
            cmd = ["ping", "-c", "1", "-W", "1000", cube_ip]

            # Execute ping command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()
            receive_time = time.time()

            if process.returncode == 0:
                # Parse ping output to extract response time
                output = stdout.decode()
                ping_time_ms = self._parse_ping_output(output)

                if ping_time_ms is not None:
                    result = {
                        'timestamp': datetime.fromtimestamp(receive_time).isoformat(),
                        'cube_id': cube_id,
                        'icmp_ping_time_ms': ping_time_ms
                    }

                    await self._write_result(result)
                    print(f"🌐 Cube {cube_id:2d}: {ping_time_ms:6.1f}ms (ICMP)")
                else:
                    # Could not parse response time
                    await self._handle_icmp_timeout(cube_id, receive_time)
            else:
                # Ping failed
                await self._handle_icmp_timeout(cube_id, receive_time)

        except Exception as e:
            print(f"⚠️  ICMP ping error for cube {cube_id}: {e}")
            await self._handle_icmp_timeout(cube_id, time.time())
        finally:
            # Remove from pending
            self.pending_icmp_pings.pop(cube_id, None)

    def _parse_ping_output(self, output):
        """Parse ping command output to extract response time"""
        try:
            # Look for patterns like "time=12.3 ms" in ping output
            match = re.search(r'time[=<](\d+\.?\d*)\s*ms', output)
            if match:
                return float(match.group(1))
        except Exception:
            pass
        return None

    async def _handle_icmp_timeout(self, cube_id, current_time):
        """Handle ICMP ping timeout or failure"""
        timeout_result = {
            'timestamp': datetime.fromtimestamp(current_time).isoformat(),
            'cube_id': cube_id,
            'icmp_ping_time_ms': None
        }

        await self._write_result(timeout_result)
        print(f"🌐 Cube {cube_id:2d}: TIMEOUT (ICMP)")

    async def check_udp_responses(self):
        """Check for UDP responses (ping, rssi, timing, temp)"""
        if not self.udp_socket:
            return

        try:
            while True:
                try:
                    data, addr = self.udp_socket.recvfrom(1024)
                    receive_time = time.time()

                    # Extract cube ID from IP address
                    cube_ip_octet = int(addr[0].split('.')[-1])
                    cube_id = cube_ip_octet - 20

                    if data == b"pong":
                        # Handle ping response
                        if cube_id in self.pending_udp_pings:
                            send_time = self.pending_udp_pings[cube_id]
                            response_time_ms = (receive_time - send_time) * 1000

                            result = {
                                'timestamp': datetime.fromtimestamp(receive_time).isoformat(),
                                'cube_id': cube_id,
                                'udp_ping_time_ms': round(response_time_ms, 1)
                            }

                            await self._write_result(result)
                            del self.pending_udp_pings[cube_id]

                            print(f"📊 Cube {cube_id:2d}: {response_time_ms:6.1f}ms (UDP)")

                    elif data.isdigit() or (data.startswith(b'-') and data[1:].isdigit()):
                        # Handle RSSI response (numeric value, possibly negative)
                        if cube_id in self.pending_rssi_requests:
                            send_time = self.pending_rssi_requests[cube_id]
                            response_time_ms = (receive_time - send_time) * 1000
                            rssi_value = int(data.decode())

                            result = {
                                'timestamp': datetime.fromtimestamp(receive_time).isoformat(),
                                'cube_id': cube_id,
                                'rssi_dbm': rssi_value,
                                'rssi_response_time_ms': round(response_time_ms, 1)
                            }

                            await self._write_result(result)
                            del self.pending_rssi_requests[cube_id]

                            print(f"📶 Cube {cube_id:2d}: {rssi_value}dBm ({response_time_ms:5.1f}ms)")

                    elif b':' in data:
                        # Handle timing or temperature response (format: "cube_id:value")
                        response_data = data.decode()
                        parts = response_data.split(':')
                        if len(parts) == 2:
                            reported_cube_id = int(parts[0])
                            value_str = parts[1]

                            # Check if this is a timing response (integer value)
                            if cube_id in self.pending_timing_requests and value_str.isdigit():
                                send_time = self.pending_timing_requests[cube_id]
                                response_time_ms = (receive_time - send_time) * 1000
                                loop_time_us = int(value_str)

                                result = {
                                    'timestamp': datetime.fromtimestamp(receive_time).isoformat(),
                                    'cube_id': cube_id,
                                    'loop_time_us': loop_time_us,
                                    'timing_response_time_ms': round(response_time_ms, 1)
                                }

                                await self._write_result(result)
                                del self.pending_timing_requests[cube_id]

                                print(f"⏱️  Cube {cube_id:2d}: loop={loop_time_us}µs ({response_time_ms:5.1f}ms)")

                            # Check if this is a temperature response (float value)
                            elif cube_id in self.pending_temp_requests:
                                try:
                                    send_time = self.pending_temp_requests[cube_id]
                                    response_time_ms = (receive_time - send_time) * 1000
                                    temperature_c = float(value_str)

                                    result = {
                                        'timestamp': datetime.fromtimestamp(receive_time).isoformat(),
                                        'cube_id': cube_id,
                                        'temperature_c': temperature_c,
                                        'temp_response_time_ms': round(response_time_ms, 1)
                                    }

                                    await self._write_result(result)
                                    del self.pending_temp_requests[cube_id]

                                    print(f"🌡️  Cube {cube_id:2d}: {temperature_c}°C ({response_time_ms:5.1f}ms)")

                                except ValueError:
                                    # Not a valid temperature float
                                    pass

                except socket.timeout:
                    break  # No more data available
                except Exception as e:
                    print(f"⚠️  UDP receive error: {e}")
                    break

        except Exception as e:
            print(f"⚠️  UDP check error: {e}")

    async def mark_udp_timeouts(self, current_time, final=False):
        """Mark old pending UDP requests as timeouts"""
        timeout_threshold = 5.0 if not final else 0.0  # 5 seconds for timeout, 0 for final

        # Handle UDP ping timeouts
        timed_out_cubes = []
        for cube_id, send_time in self.pending_udp_pings.items():
            if (current_time - send_time) > timeout_threshold:
                timed_out_cubes.append(cube_id)

        for cube_id in timed_out_cubes:
            timeout_result = {
                'timestamp': datetime.fromtimestamp(current_time).isoformat(),
                'cube_id': cube_id,
                'udp_ping_time_ms': None
            }

            await self._write_result(timeout_result)
            del self.pending_udp_pings[cube_id]

            if not final:  # Don't spam during final cleanup
                print(f"⏱️  Cube {cube_id:2d}: TIMEOUT (UDP)")

        # Handle RSSI request timeouts
        timed_out_rssi = []
        for cube_id, send_time in self.pending_rssi_requests.items():
            if (current_time - send_time) > timeout_threshold:
                timed_out_rssi.append(cube_id)

        for cube_id in timed_out_rssi:
            timeout_result = {
                'timestamp': datetime.fromtimestamp(current_time).isoformat(),
                'cube_id': cube_id,
                'rssi_dbm': None,
                'rssi_response_time_ms': None
            }

            await self._write_result(timeout_result)
            del self.pending_rssi_requests[cube_id]

            if not final:  # Don't spam during final cleanup
                print(f"📶 Cube {cube_id:2d}: RSSI TIMEOUT")

        # Handle timing request timeouts
        timed_out_timing = []
        for cube_id, send_time in self.pending_timing_requests.items():
            if (current_time - send_time) > timeout_threshold:
                timed_out_timing.append(cube_id)

        for cube_id in timed_out_timing:
            timeout_result = {
                'timestamp': datetime.fromtimestamp(current_time).isoformat(),
                'cube_id': cube_id,
                'loop_time_us': None,
                'timing_response_time_ms': None
            }

            await self._write_result(timeout_result)
            del self.pending_timing_requests[cube_id]

            if not final:  # Don't spam during final cleanup
                print(f"⏱️  Cube {cube_id:2d}: TIMING TIMEOUT")

        # Handle temperature request timeouts
        timed_out_temp = []
        for cube_id, send_time in self.pending_temp_requests.items():
            if (current_time - send_time) > timeout_threshold:
                timed_out_temp.append(cube_id)

        for cube_id in timed_out_temp:
            timeout_result = {
                'timestamp': datetime.fromtimestamp(current_time).isoformat(),
                'cube_id': cube_id,
                'temperature_c': None,
                'temp_response_time_ms': None
            }

            await self._write_result(timeout_result)
            del self.pending_temp_requests[cube_id]

            if not final:  # Don't spam during final cleanup
                print(f"🌡️  Cube {cube_id:2d}: TEMP TIMEOUT")

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
        print(f"📡 Protocols: MQTT + UDP (ping/rssi/timing/temp) + ICMP")
        print()

        # Setup UDP socket
        self.setup_udp()

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

                        # Send MQTT, UDP, and ICMP requests to all cubes simultaneously
                        ping_tasks = []
                        for cube_id in self.cube_ids:
                            task = self._send_ping(client, cube_id, ping_count, current_time)
                            ping_tasks.append(task)
                            await self.send_udp_ping(cube_id, current_time)
                            await self.send_rssi_request(cube_id, current_time)
                            await self.send_timing_request(cube_id, current_time)
                            await self.send_temp_request(cube_id, current_time)
                            await self.send_icmp_ping(cube_id, current_time)

                        await asyncio.gather(*ping_tasks)

                        # Check for UDP responses
                        await self.check_udp_responses()

                        # Mark timeouts for pings that are too old (>5 seconds)
                        await self._mark_timeouts(f, current_time)
                        await self.mark_udp_timeouts(current_time)

                        # Wait for next ping cycle (1 second)
                        await asyncio.sleep(1.0)

                    # Final timeout check
                    await self._mark_timeouts(f, time.time(), final=True)
                    await self.mark_udp_timeouts(time.time(), final=True)

                # Cancel listener task
                listen_task.cancel()
                try:
                    await listen_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            print(f"❌ Error during monitoring: {e}")
            raise
        finally:
            # Cleanup UDP socket
            if self.udp_socket:
                self.udp_socket.close()

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
                        'mqtt_ping_time_ms': round(response_time_ms, 1)
                    }

                    # Write immediately to file
                    await self._write_result(result)

                    # Remove from pending
                    del self.pending_pings[ping_id]

                    print(f"📊 Cube {cube_id:2d}: {response_time_ms:6.1f}ms (MQTT)")
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
                'mqtt_ping_time_ms': None
            }

            # Write timeout to file
            file_handle.write(json.dumps(timeout_result) + '\n')
            file_handle.flush()

            # Remove from pending
            del self.pending_pings[ping_id]

            if not final:  # Don't spam during final cleanup
                print(f"⏱️  Cube {cube_id:2d}: TIMEOUT (MQTT)")


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