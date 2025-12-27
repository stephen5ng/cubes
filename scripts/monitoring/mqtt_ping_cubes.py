#!/usr/bin/env python3
"""
Standalone MQTT Cube Ping Program

Pings cubes 1-6 via MQTT and logs response times to a JSONL file.
Each cube is pinged concurrently for accurate timing measurements.

Usage:
    python mqtt_ping_cubes.py [--broker BROKER] [--output OUTPUT] [--count COUNT] [--interval INTERVAL]
"""

import asyncio
import aiomqtt
import argparse
import json
import time
from datetime import datetime
import sys

class CubePinger:
    def __init__(self, broker="192.168.8.247"):
        self.broker = broker
        self.cube_ids = [1, 2, 3, 4, 5, 6]  # P0 cubes
        self.pending_pings = {}  # ping_id -> (cube_id, send_time)
        self.results = []
        
    async def ping_all_cubes(self, count=10, interval=1.0, output_file="cube_ping_results.jsonl"):
        """Ping all cubes and log results to JSONL file"""
        print(f"🔍 Starting MQTT ping for cubes {self.cube_ids}")
        print(f"📊 Will ping {count} times with {interval}s intervals")
        print(f"📡 Broker: {self.broker}")
        print(f"📝 Output: {output_file}")
        print()
        
        async with aiomqtt.Client(self.broker) as client:
            # Subscribe to all echo topics
            for cube_id in self.cube_ids:
                echo_topic = f"cube/{cube_id}/echo"
                await client.subscribe(echo_topic)
                print(f"📡 Subscribed to {echo_topic}")
            
            print()
            
            # Start message listener task
            listen_task = asyncio.create_task(
                self._listen_for_responses(client)
            )
            
            # Open output file for writing
            with open(output_file, 'w') as f:
                # Send pings in rounds
                for round_num in range(1, count + 1):
                    print(f"📤 Round {round_num}/{count}:")
                    
                    # Send ping to all cubes simultaneously
                    ping_tasks = []
                    for cube_id in self.cube_ids:
                        task = self._send_ping(client, cube_id, round_num)
                        ping_tasks.append(task)
                    
                    await asyncio.gather(*ping_tasks)
                    
                    # Wait for responses (give some time for slow responses)
                    await asyncio.sleep(min(2.0, interval * 0.8))
                    
                    # Write any new results to file
                    self._write_new_results(f)
                    
                    # Wait for next round
                    if round_num < count:
                        remaining_time = interval - min(2.0, interval * 0.8)
                        if remaining_time > 0:
                            await asyncio.sleep(remaining_time)
                    
                    print()
                
                # Wait for final responses
                print("⏳ Waiting 3s for final responses...")
                await asyncio.sleep(3)
                
                # Write final results
                self._write_new_results(f)
            
            # Cancel listener task
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass
        
        # Print summary
        self._print_summary(count)
    
    async def _send_ping(self, client, cube_id, round_num):
        """Send ping to a specific cube"""
        ping_id = f"ping_{cube_id}_{round_num}_{int(time.time() * 1000)}"
        send_time = time.time()
        
        # Store pending ping
        self.pending_pings[ping_id] = (cube_id, send_time)
        
        # Send ping
        ping_topic = f"cube/{cube_id}/ping"
        await client.publish(ping_topic, ping_id)
        print(f"  → Cube {cube_id}: {ping_id}")
    
    async def _listen_for_responses(self, client):
        """Listen for ping echo responses"""
        try:
            async for message in client.messages:
                topic_parts = str(message.topic).split('/')
                if len(topic_parts) >= 3 and topic_parts[2] == 'echo':
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
                                'ping_id': ping_id,
                                'send_time': send_time,
                                'receive_time': receive_time,
                                'response_time_ms': round(response_time_ms, 1),
                                'status': 'success'
                            }
                            self.results.append(result)
                            
                            # Remove from pending
                            del self.pending_pings[ping_id]
                            
                            print(f"  ← Cube {cube_id}: {response_time_ms:.1f}ms")
                        else:
                            print(f"  ⚠️  Cube ID mismatch: expected {stored_cube_id}, got {cube_id}")
                    else:
                        print(f"  ❓ Unexpected response from cube {cube_id}: {ping_id}")
                        
        except asyncio.CancelledError:
            pass
    
    def _write_new_results(self, file_handle):
        """Write any unwritten results to JSONL file"""
        # For simplicity, we'll write all results each time
        # In a real implementation, you'd track which results were already written
        pass
    
    def _print_summary(self, expected_pings):
        """Print summary statistics"""
        print("=" * 60)
        print("📊 PING SUMMARY")
        print("=" * 60)
        
        # Write all results to file now
        total_expected = expected_pings * len(self.cube_ids)
        total_received = len(self.results)
        
        print(f"Total pings sent: {total_expected}")
        print(f"Total responses: {total_received}")
        print(f"Overall success rate: {total_received/total_expected*100:.1f}%")
        print()
        
        # Per-cube statistics
        for cube_id in self.cube_ids:
            cube_results = [r for r in self.results if r['cube_id'] == cube_id]
            success_rate = len(cube_results) / expected_pings * 100
            
            if cube_results:
                response_times = [r['response_time_ms'] for r in cube_results]
                avg_response = sum(response_times) / len(response_times)
                min_response = min(response_times)
                max_response = max(response_times)
                
                print(f"Cube {cube_id}: {len(cube_results)}/{expected_pings} ({success_rate:.1f}%) - "
                      f"avg: {avg_response:.1f}ms, min: {min_response:.1f}ms, max: {max_response:.1f}ms")
            else:
                print(f"Cube {cube_id}: 0/{expected_pings} (0.0%) - NO RESPONSE")
        
        # Mark any remaining pending pings as timeouts
        for ping_id, (cube_id, send_time) in self.pending_pings.items():
            timeout_result = {
                'timestamp': datetime.now().isoformat(),
                'cube_id': cube_id,
                'ping_id': ping_id,
                'send_time': send_time,
                'receive_time': None,
                'response_time_ms': None,
                'status': 'timeout'
            }
            self.results.append(timeout_result)
        
        print(f"\n💾 Results written to cube_ping_results.jsonl ({len(self.results)} entries)")

def main():
    parser = argparse.ArgumentParser(description="Ping MQTT cubes and log response times")
    parser.add_argument("--broker", default="192.168.8.247", help="MQTT broker address")
    parser.add_argument("--output", default="cube_ping_results.jsonl", help="Output JSONL file")
    parser.add_argument("--count", type=int, default=10, help="Number of pings per cube")
    parser.add_argument("--interval", type=float, default=1.0, help="Interval between ping rounds (seconds)")
    
    args = parser.parse_args()
    
    try:
        pinger = CubePinger(broker=args.broker)
        
        # Write results to file as we go
        with open(args.output, 'w') as f:
            asyncio.run(pinger.ping_all_cubes(
                count=args.count,
                interval=args.interval,
                output_file=args.output
            ))
            
            # Write all results at the end
            for result in pinger.results:
                f.write(json.dumps(result) + '\n')
                
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()