#!/usr/bin/env python3
"""
Monitor ESP32 cube behavior to see if they're contributing to latency issues.
"""

import asyncio
import time
import paho.mqtt.client as mqtt
from collections import defaultdict
import json

class ESP32Monitor:
    def __init__(self, mqtt_host="192.168.8.247"):
        self.mqtt_host = mqtt_host
        self.running = True
        
        # Track different types of messages from cubes
        self.cube_messages = defaultdict(list)  # cube_id -> [(timestamp, topic, message)]
        self.cube_neighbors = defaultdict(list)  # Track neighbor reports
        self.cube_status = defaultdict(dict)  # Track cube status
        
        self.client = mqtt.Client(client_id="esp32_monitor")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected with result code {rc}")
        # Subscribe to all cube topics
        client.subscribe("cube/+/+")
        
    def on_message(self, client, userdata, msg):
        timestamp = time.time()
        topic_parts = msg.topic.split('/')
        
        if len(topic_parts) >= 3 and topic_parts[0] == "cube":
            cube_id = int(topic_parts[1])
            topic_type = topic_parts[2]
            message = msg.payload.decode()
            
            self.cube_messages[cube_id].append((timestamp, topic_type, message))
            
            # Track specific message types
            if topic_type == "right":
                self.cube_neighbors[cube_id].append((timestamp, message))
            elif topic_type in ["letter", "border", "flash"]:
                self.cube_status[cube_id][topic_type] = (timestamp, message)
                
            # Print real-time updates for debugging
            print(f"Cube {cube_id:2d} {topic_type:8s}: {message}")
            
    async def monitor(self, duration_seconds=60):
        """Monitor ESP32 cube behavior"""
        print(f"Monitoring ESP32 cubes for {duration_seconds} seconds...")
        print("Looking for unusual patterns, excessive messages, or timing issues")
        print("-" * 60)
        
        try:
            self.client.connect(self.mqtt_host, 1883, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"Failed to connect: {e}")
            return
            
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration_seconds and self.running:
                await asyncio.sleep(0.1)
        except KeyboardInterrupt:
            print("\nMonitoring interrupted")
            self.running = False
            
        self.client.loop_stop()
        self.client.disconnect()
        
        self.analyze_behavior()
        
    def analyze_behavior(self):
        """Analyze ESP32 behavior patterns"""
        print("\n" + "="*60)
        print("ESP32 BEHAVIOR ANALYSIS")
        print("="*60)
        
        # Overall message statistics
        total_messages = sum(len(messages) for messages in self.cube_messages.values())
        print(f"Total messages received: {total_messages}")
        print(f"Active cubes: {sorted(self.cube_messages.keys())}")
        
        # Per-cube analysis
        for cube_id in sorted(self.cube_messages.keys()):
            messages = self.cube_messages[cube_id]
            if not messages:
                continue
                
            print(f"\nCube {cube_id}:")
            print(f"  Total messages: {len(messages)}")
            
            # Message type breakdown
            message_types = defaultdict(int)
            for _, msg_type, _ in messages:
                message_types[msg_type] += 1
                
            for msg_type, count in sorted(message_types.items()):
                print(f"  {msg_type}: {count}")
                
            # Check for excessive neighbor reports (potential WiFi issues)
            neighbor_reports = self.cube_neighbors.get(cube_id, [])
            if neighbor_reports:
                print(f"  Neighbor reports: {len(neighbor_reports)}")
                
                # Check for rapid neighbor changes (indicates connectivity issues)
                if len(neighbor_reports) > 1:
                    rapid_changes = 0
                    for i in range(1, len(neighbor_reports)):
                        time_diff = neighbor_reports[i][0] - neighbor_reports[i-1][0]
                        if time_diff < 1.0:  # Changes within 1 second
                            rapid_changes += 1
                            
                    if rapid_changes > 0:
                        print(f"  Rapid neighbor changes: {rapid_changes} (potential connectivity issues)")
                        
                # Show recent neighbor reports
                recent_neighbors = neighbor_reports[-5:]
                print("  Recent neighbors:", [report[1] for report in recent_neighbors])
                
        # Look for timing patterns that might indicate problems
        print(f"\nTiming Analysis:")
        
        # Check for cubes that might be overloading the network
        message_rates = {}
        for cube_id, messages in self.cube_messages.items():
            if len(messages) > 1:
                time_span = messages[-1][0] - messages[0][0]
                if time_span > 0:
                    rate = len(messages) / time_span
                    message_rates[cube_id] = rate
                    
        if message_rates:
            avg_rate = sum(message_rates.values()) / len(message_rates)
            print(f"  Average message rate: {avg_rate:.2f} msg/sec")
            
            # Find cubes with unusually high message rates
            high_rate_cubes = {cube_id: rate for cube_id, rate in message_rates.items() 
                             if rate > avg_rate * 2}
            
            if high_rate_cubes:
                print("  High-rate cubes (>2x average):")
                for cube_id, rate in sorted(high_rate_cubes.items()):
                    print(f"    Cube {cube_id}: {rate:.2f} msg/sec")
                    
        # Check for missing cubes (should be 1-6, 11-16)
        expected_cubes = set(range(1, 7)) | set(range(11, 17))
        active_cubes = set(self.cube_messages.keys())
        missing_cubes = expected_cubes - active_cubes
        
        if missing_cubes:
            print(f"  Missing cubes: {sorted(missing_cubes)}")
            print("  (These cubes might be offline or having connectivity issues)")

async def main():
    monitor = ESP32Monitor()
    
    import signal
    def signal_handler(sig, frame):
        monitor.running = False
        
    signal.signal(signal.SIGINT, signal_handler)
    
    print("ESP32 Cube Monitor")
    print("This will show all MQTT messages from cubes to identify potential issues.")
    print("Press Ctrl+C to stop monitoring and see analysis.")
    print()
    
    await monitor.monitor(duration_seconds=60)

if __name__ == "__main__":
    asyncio.run(main())