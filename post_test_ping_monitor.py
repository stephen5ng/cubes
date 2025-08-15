#!/usr/bin/env python3
"""
Post-Test Ping Monitor

Pings cubes after functional tests to measure when they finish processing
their message backlog. Measures ping response times to detect when cubes
have caught up with queued messages.
"""

import asyncio
import aiomqtt
import argparse
import json
import time
from datetime import datetime

class CubePingMonitor:
    def __init__(self, broker="192.168.8.247", cube_id="1"):
        self.broker = broker
        self.cube_id = cube_id
        self.ping_topic = f"cube/{cube_id}/ping"
        self.echo_topic = f"cube/{cube_id}/echo"
        self.pending_pings = {}  # timestamp -> ping_id mapping
        
    async def monitor_post_test_activity(self, duration_seconds=60, ping_interval=2):
        """Monitor cube responsiveness after test completion"""
        print(f"🔍 Starting post-test ping monitoring for cube {self.cube_id}")
        print(f"📊 Will ping every {ping_interval}s for {duration_seconds}s")
        print(f"📡 Broker: {self.broker}")
        print()
        
        results = []
        
        async with aiomqtt.Client(self.broker) as client:
            # Subscribe to echo responses
            await client.subscribe(self.echo_topic)
            
            # Start message listener task
            listen_task = asyncio.create_task(
                self._listen_for_responses(client, results)
            )
            
            # Send pings at regular intervals
            ping_count = 0
            start_time = time.time()
            
            try:
                while time.time() - start_time < duration_seconds:
                    ping_count += 1
                    ping_id = f"ping_{ping_count}_{int(time.time() * 1000)}"
                    send_time = time.time()
                    
                    # Store pending ping
                    self.pending_pings[ping_id] = send_time
                    
                    # Send ping
                    await client.publish(self.ping_topic, ping_id)
                    print(f"📤 Sent ping {ping_count}: {ping_id}")
                    
                    # Wait for next ping
                    await asyncio.sleep(ping_interval)
                    
            except KeyboardInterrupt:
                print("\n⏹️  Monitoring stopped by user")
            
            # Wait a bit for final responses
            print("\n⏳ Waiting 5s for final responses...")
            await asyncio.sleep(5)
            
            # Cancel listener task
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass
        
        # Analyze results
        self._analyze_results(results, ping_count)
    
    async def _listen_for_responses(self, client, results):
        """Listen for ping echo responses"""
        try:
            async for message in client.messages:
                if message.topic.matches(self.echo_topic):
                    receive_time = time.time()
                    ping_id = message.payload.decode()
                    
                    if ping_id in self.pending_pings:
                        send_time = self.pending_pings[ping_id]
                        response_time_ms = (receive_time - send_time) * 1000
                        
                        result = {
                            'ping_id': ping_id,
                            'send_time': send_time,
                            'receive_time': receive_time,
                            'response_time_ms': response_time_ms,
                            'timestamp': datetime.fromtimestamp(receive_time).isoformat()
                        }
                        results.append(result)
                        
                        # Remove from pending
                        del self.pending_pings[ping_id]
                        
                        print(f"📥 Response: {ping_id} -> {response_time_ms:.1f}ms")
                    else:
                        print(f"❓ Unexpected response: {ping_id}")
                        
        except asyncio.CancelledError:
            # Task was cancelled, clean exit
            pass
    
    def _analyze_results(self, results, total_pings):
        """Analyze ping results to detect patterns"""
        print()
        print("=" * 60)
        print("📊 POST-TEST PING ANALYSIS")
        print("=" * 60)
        
        if not results:
            print(f"❌ No responses received out of {total_pings} pings sent")
            print("   - Cube may be offline")
            print("   - Cube may be severely overloaded")
            return
        
        response_times = [r['response_time_ms'] for r in results]
        response_rate = len(results) / total_pings * 100
        
        print(f"📈 Response Statistics:")
        print(f"   Responses received: {len(results)}/{total_pings} ({response_rate:.1f}%)")
        print(f"   Average response time: {sum(response_times)/len(response_times):.1f}ms")
        print(f"   Min response time: {min(response_times):.1f}ms")
        print(f"   Max response time: {max(response_times):.1f}ms")
        print()
        
        # Analyze trends over time
        if len(results) >= 5:
            first_half = response_times[:len(response_times)//2]
            second_half = response_times[len(response_times)//2:]
            
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)
            
            print(f"📉 Trend Analysis:")
            print(f"   First half average: {first_avg:.1f}ms")
            print(f"   Second half average: {second_avg:.1f}ms")
            
            if second_avg < first_avg * 0.8:
                print(f"   ✅ IMPROVING: Response times decreased by {((first_avg - second_avg)/first_avg*100):.1f}%")
                print(f"      → Cube appears to be catching up with backlog")
            elif second_avg > first_avg * 1.2:
                print(f"   ⚠️  DEGRADING: Response times increased by {((second_avg - first_avg)/first_avg*100):.1f}%")
                print(f"      → Cube may be falling further behind")
            else:
                print(f"   ➡️  STABLE: Response times relatively consistent")
        
        print()
        
        # Categorize response times
        fast_responses = [t for t in response_times if t < 100]
        slow_responses = [t for t in response_times if t >= 1000]
        
        print(f"🚦 Response Time Categories:")
        print(f"   Fast (<100ms): {len(fast_responses)} ({len(fast_responses)/len(response_times)*100:.1f}%)")
        print(f"   Normal (100-1000ms): {len(response_times) - len(fast_responses) - len(slow_responses)} ({(len(response_times) - len(fast_responses) - len(slow_responses))/len(response_times)*100:.1f}%)")
        print(f"   Slow (≥1000ms): {len(slow_responses)} ({len(slow_responses)/len(response_times)*100:.1f}%)")
        
        if len(slow_responses) > 0:
            print(f"   ⚠️  {len(slow_responses)} slow responses indicate backlog processing")
        
        # Save detailed results
        with open('post_test_ping_results.json', 'w') as f:
            json.dump({
                'summary': {
                    'total_pings': total_pings,
                    'responses_received': len(results),
                    'response_rate_percent': response_rate,
                    'avg_response_ms': sum(response_times)/len(response_times) if response_times else 0,
                    'min_response_ms': min(response_times) if response_times else 0,
                    'max_response_ms': max(response_times) if response_times else 0
                },
                'results': results
            }, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: post_test_ping_results.json")


async def main():
    parser = argparse.ArgumentParser(description="Monitor cube responsiveness after functional tests")
    parser.add_argument("--broker", default="192.168.8.247", help="MQTT broker address")
    parser.add_argument("--cube-id", default="1", help="Cube ID to monitor")
    parser.add_argument("--duration", type=int, default=60, help="Monitor duration in seconds")
    parser.add_argument("--interval", type=int, default=2, help="Ping interval in seconds")
    
    args = parser.parse_args()
    
    monitor = CubePingMonitor(broker=args.broker, cube_id=args.cube_id)
    await monitor.monitor_post_test_activity(
        duration_seconds=args.duration, 
        ping_interval=args.interval
    )


if __name__ == "__main__":
    asyncio.run(main())