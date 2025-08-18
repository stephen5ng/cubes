#!/usr/bin/env python3
"""
Diagnose MQTT latency issues by measuring timing of MQTT operations.
"""

import asyncio
import time
import statistics
import paho.mqtt.client as mqtt
from collections import defaultdict, deque
import threading
import signal
import sys

class LatencyDiagnostic:
    def __init__(self, mqtt_host="192.168.8.247"):
        self.mqtt_host = mqtt_host
        self.publish_times = {}  # message_id -> timestamp
        self.latencies = []
        self.receive_times = deque(maxlen=100)  # Rolling window of receive times
        self.last_receive_time = None
        self.message_gaps = []
        self.running = True
        
        # MQTT client for publishing
        self.pub_client = mqtt.Client(client_id="latency_pub")
        self.pub_client.on_publish = self.on_publish
        
        # MQTT client for subscribing
        self.sub_client = mqtt.Client(client_id="latency_sub")
        self.sub_client.on_connect = self.on_connect
        self.sub_client.on_message = self.on_message
        
    def on_connect(self, client, userdata, flags, rc):
        print(f"Subscriber connected with result code {rc}")
        client.subscribe("cube/+/letter")
        
    def on_publish(self, client, userdata, mid):
        """Called when publish is complete"""
        if mid in self.publish_times:
            latency = (time.time() - self.publish_times[mid]) * 1000
            self.latencies.append(latency)
            del self.publish_times[mid]
            
    def on_message(self, client, userdata, msg):
        """Called when we receive a message"""
        now = time.time()
        self.receive_times.append(now)
        
        # Calculate gap since last message
        if self.last_receive_time:
            gap = (now - self.last_receive_time) * 1000
            self.message_gaps.append(gap)
            
        self.last_receive_time = now
        
    async def run_diagnostic(self, duration_seconds=30):
        """Run latency diagnostic for specified duration"""
        print(f"Starting latency diagnostic for {duration_seconds} seconds...")
        print(f"MQTT Host: {self.mqtt_host}")
        
        # Connect clients
        try:
            self.pub_client.connect(self.mqtt_host, 1883, 60)
            self.sub_client.connect(self.mqtt_host, 1883, 60)
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            return
            
        # Start network loops
        self.pub_client.loop_start()
        self.sub_client.loop_start()
        
        await asyncio.sleep(1)  # Let connections establish
        
        start_time = time.time()
        message_count = 0
        
        try:
            while time.time() - start_time < duration_seconds and self.running:
                # Send test message
                test_letter = chr(ord('A') + (message_count % 26))
                cube_id = 11 + (message_count % 6)
                
                # Record publish time
                mid = message_count
                self.publish_times[mid] = time.time()
                
                # Publish with message ID
                result = self.pub_client.publish(
                    f"cube/{cube_id}/letter", 
                    test_letter,
                    qos=0
                )
                
                # Store message ID for latency tracking
                self.publish_times[result.mid] = self.publish_times.pop(mid)
                
                message_count += 1
                await asyncio.sleep(0.1)  # 100ms between messages
                
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            self.running = False
            
        # Stop clients
        self.pub_client.loop_stop()
        self.sub_client.loop_stop()
        self.pub_client.disconnect()
        self.sub_client.disconnect()
        
        self.print_results()
        
    def print_results(self):
        """Print diagnostic results"""
        print("\n" + "="*50)
        print("LATENCY DIAGNOSTIC RESULTS")
        print("="*50)
        
        if self.latencies:
            print(f"\nPublish Latencies (ms):")
            print(f"  Count: {len(self.latencies)}")
            print(f"  Mean: {statistics.mean(self.latencies):.2f}")
            print(f"  Median: {statistics.median(self.latencies):.2f}")
            print(f"  Min: {min(self.latencies):.2f}")
            print(f"  Max: {max(self.latencies):.2f}")
            if len(self.latencies) > 1:
                print(f"  Std Dev: {statistics.stdev(self.latencies):.2f}")
                
            # Find outliers (> 95th percentile)
            sorted_latencies = sorted(self.latencies)
            p95_idx = int(0.95 * len(sorted_latencies))
            p95_threshold = sorted_latencies[p95_idx]
            outliers = [l for l in self.latencies if l > p95_threshold]
            if outliers:
                print(f"  Outliers (>95th percentile): {len(outliers)} messages")
                print(f"  Outlier threshold: {p95_threshold:.2f}ms")
                
        if self.message_gaps:
            print(f"\nMessage Receive Gaps (ms):")
            print(f"  Count: {len(self.message_gaps)}")
            print(f"  Mean: {statistics.mean(self.message_gaps):.2f}")
            print(f"  Median: {statistics.median(self.message_gaps):.2f}")
            print(f"  Min: {min(self.message_gaps):.2f}")
            print(f"  Max: {max(self.message_gaps):.2f}")
            
            # Find large gaps (potential network issues)
            large_gaps = [g for g in self.message_gaps if g > 200]  # >200ms gaps
            if large_gaps:
                print(f"  Large gaps (>200ms): {len(large_gaps)}")
                print(f"  Largest gap: {max(large_gaps):.2f}ms")
                
        # Throughput analysis
        if len(self.receive_times) > 1:
            total_time = self.receive_times[-1] - self.receive_times[0]
            throughput = (len(self.receive_times) - 1) / total_time
            print(f"\nThroughput: {throughput:.2f} messages/second")

async def main():
    diagnostic = LatencyDiagnostic()
    
    def signal_handler(sig, frame):
        print("\nShutting down...")
        diagnostic.running = False
        
    signal.signal(signal.SIGINT, signal_handler)
    
    await diagnostic.run_diagnostic(duration_seconds=30)

if __name__ == "__main__":
    asyncio.run(main())