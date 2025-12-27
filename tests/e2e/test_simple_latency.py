#!/usr/bin/env python3
"""
Simple latency test that mimics random_letters.sh behavior
"""

import asyncio
import time
import subprocess
import paho.mqtt.client as mqtt
import statistics
import signal
import sys

class SimpleLatencyTest:
    def __init__(self, mqtt_host="192.168.8.247"):
        self.mqtt_host = mqtt_host
        self.running = True
        self.received_messages = []
        self.sent_messages = []
        
    async def test_latency_pattern(self):
        """Test the exact pattern from random_letters.sh"""
        print("Testing random_letters.sh pattern...")
        
        # Subscribe to messages
        sub_client = mqtt.Client(client_id="latency_subscriber")
        
        def on_message(client, userdata, msg):
            receive_time = time.time()
            cube_id = int(msg.topic.split('/')[1])
            letter = msg.payload.decode()
            self.received_messages.append((receive_time, cube_id, letter))
            
        def on_connect(client, userdata, flags, rc):
            for cube_id in [11, 12, 13, 14, 15, 16]:
                client.subscribe(f"cube/{cube_id}/letter")
                
        sub_client.on_connect = on_connect
        sub_client.on_message = on_message
        
        try:
            sub_client.connect(self.mqtt_host, 1883, 60)
            sub_client.loop_start()
        except Exception as e:
            print(f"Failed to connect subscriber: {e}")
            return
            
        await asyncio.sleep(1)  # Let subscriber connect
        
        # Send letters like random_letters.sh does
        pub_client = mqtt.Client(client_id="latency_publisher")
        try:
            pub_client.connect(self.mqtt_host, 1883, 60)
        except Exception as e:
            print(f"Failed to connect publisher: {e}")
            return
            
        print("Sending letters A-Z to cubes 11-16...")
        
        letter_ord = ord('A')
        for cycle in range(3):  # Send 3 cycles to see patterns
            for i in range(26):  # A-Z
                letter = chr(letter_ord + i)
                send_time = time.time()
                
                # Send to all cubes like random_letters.sh
                for cube_id in [11, 12, 13, 14, 15, 16]:
                    pub_client.publish(f"cube/{cube_id}/letter", letter)
                    self.sent_messages.append((send_time, cube_id, letter))
                    
                print(f"Sent {letter} to cubes 11-16")
                
                # Wait 250ms like random_letters.sh
                await asyncio.sleep(0.25)
                
                if not self.running:
                    break
                    
            if not self.running:
                break
                
        # Wait a bit for final messages
        await asyncio.sleep(2)
        
        pub_client.disconnect()
        sub_client.loop_stop()
        sub_client.disconnect()
        
        self.analyze_latency_results()
        
    def analyze_latency_results(self):
        """Analyze the send/receive timing"""
        print("\n" + "="*50)
        print("LATENCY ANALYSIS")
        print("="*50)
        
        print(f"Sent messages: {len(self.sent_messages)}")
        print(f"Received messages: {len(self.received_messages)}")
        
        # Calculate message-to-message intervals for received messages
        if len(self.received_messages) > 1:
            intervals = []
            for i in range(1, len(self.received_messages)):
                interval = (self.received_messages[i][0] - self.received_messages[i-1][0]) * 1000
                intervals.append(interval)
                
            print(f"\nReceived Message Intervals (ms):")
            print(f"  Mean: {statistics.mean(intervals):.2f}")
            print(f"  Median: {statistics.median(intervals):.2f}")
            print(f"  Min: {min(intervals):.2f}")
            print(f"  Max: {max(intervals):.2f}")
            print(f"  Std Dev: {statistics.stdev(intervals):.2f}")
            
            # Expected interval is ~41.7ms (250ms / 6 cubes)
            expected_interval = 250.0 / 6
            print(f"  Expected interval: {expected_interval:.2f}ms")
            
            # Find problematic intervals
            slow_intervals = [i for i in intervals if i > expected_interval * 2]
            very_slow = [i for i in intervals if i > 200]
            
            if slow_intervals:
                print(f"  Slow intervals (>{expected_interval*2:.1f}ms): {len(slow_intervals)}")
                
            if very_slow:
                print(f"  Very slow intervals (>200ms): {len(very_slow)}")
                print(f"  Slowest: {max(very_slow):.2f}ms")
                
        # Check for missing messages
        expected_total = len(self.sent_messages)
        if len(self.received_messages) < expected_total:
            missing = expected_total - len(self.received_messages)
            print(f"\nMissing messages: {missing} ({missing/expected_total*100:.1f}%)")
            
        # Show timing distribution
        if len(self.received_messages) > 10:
            print(f"\nFirst 10 received messages:")
            for i, (timestamp, cube_id, letter) in enumerate(self.received_messages[:10]):
                if i > 0:
                    prev_time = self.received_messages[i-1][0]
                    gap = (timestamp - prev_time) * 1000
                    print(f"  {i+1:2d}: Cube {cube_id} = {letter} (+{gap:5.1f}ms)")
                else:
                    print(f"  {i+1:2d}: Cube {cube_id} = {letter}")

async def main():
    test = SimpleLatencyTest()
    
    def signal_handler(sig, frame):
        test.running = False
        
    signal.signal(signal.SIGINT, signal_handler)
    
    await test.test_latency_pattern()

if __name__ == "__main__":
    asyncio.run(main())