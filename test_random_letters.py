#!/usr/bin/env python3
"""
Test the random_letters.sh pattern to identify latency issues.
"""

import asyncio
import time
import subprocess
import threading
import paho.mqtt.client as mqtt
from collections import defaultdict
import statistics
import signal
import sys

class RandomLettersTest:
    def __init__(self, mqtt_host="192.168.8.247"):
        self.mqtt_host = mqtt_host
        self.running = True
        self.cube_updates = defaultdict(list)  # cube_id -> [(timestamp, letter), ...]
        self.message_intervals = []
        self.last_message_time = None
        
        # Subscribe to cube updates
        self.client = mqtt.Client(client_id="random_letters_test")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to the cubes that random_letters.sh uses
        for cube_id in [11, 12, 13, 14, 15, 16]:
            client.subscribe(f"cube/{cube_id}/letter")
            
    def on_message(self, client, userdata, msg):
        now = time.time()
        cube_id = int(msg.topic.split('/')[1])
        letter = msg.payload.decode()
        
        self.cube_updates[cube_id].append((now, letter))
        
        # Track message intervals
        if self.last_message_time:
            interval = (now - self.last_message_time) * 1000
            self.message_intervals.append(interval)
            
        self.last_message_time = now
        
        print(f"Cube {cube_id}: {letter} (interval: {interval:.1f}ms)" if self.last_message_time else f"Cube {cube_id}: {letter}")
        
    async def run_test(self, duration_seconds=60):
        """Run the test while monitoring cube updates"""
        print(f"Starting random letters test for {duration_seconds} seconds...")
        
        # Connect to MQTT
        try:
            self.client.connect(self.mqtt_host, 1883, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"Failed to connect to MQTT: {e}")
            return
            
        print("Connected, monitoring cube updates...")
        print("Run './random_letters.sh' in another terminal to start the test")
        
        # Wait for the specified duration
        start_time = time.time()
        try:
            while time.time() - start_time < duration_seconds and self.running:
                await asyncio.sleep(0.1)
        except KeyboardInterrupt:
            print("\nTest interrupted")
            self.running = False
            
        self.client.loop_stop()
        self.client.disconnect()
        
        self.analyze_results()
        
    def analyze_results(self):
        """Analyze the timing patterns"""
        print("\n" + "="*60)
        print("RANDOM LETTERS TEST RESULTS")
        print("="*60)
        
        # Overall message intervals
        if self.message_intervals:
            print(f"\nMessage Intervals (ms):")
            print(f"  Total messages: {len(self.message_intervals)}")
            print(f"  Mean interval: {statistics.mean(self.message_intervals):.2f}")
            print(f"  Median interval: {statistics.median(self.message_intervals):.2f}")
            print(f"  Min interval: {min(self.message_intervals):.2f}")
            print(f"  Max interval: {max(self.message_intervals):.2f}")
            print(f"  Std deviation: {statistics.stdev(self.message_intervals):.2f}")
            
            # Find problematic intervals
            slow_messages = [i for i in self.message_intervals if i > 100]  # >100ms
            very_slow = [i for i in self.message_intervals if i > 500]  # >500ms
            
            if slow_messages:
                print(f"  Slow updates (>100ms): {len(slow_messages)} ({len(slow_messages)/len(self.message_intervals)*100:.1f}%)")
                
            if very_slow:
                print(f"  Very slow updates (>500ms): {len(very_slow)}")
                print(f"  Slowest interval: {max(very_slow):.2f}ms")
                
        # Per-cube analysis
        print(f"\nPer-Cube Analysis:")
        for cube_id in sorted(self.cube_updates.keys()):
            updates = self.cube_updates[cube_id]
            if len(updates) > 1:
                intervals = []
                for i in range(1, len(updates)):
                    interval = (updates[i][0] - updates[i-1][0]) * 1000
                    intervals.append(interval)
                    
                print(f"  Cube {cube_id}: {len(updates)} updates, "
                      f"avg interval: {statistics.mean(intervals):.1f}ms, "
                      f"max: {max(intervals):.1f}ms")
                      
        # Letter sequence analysis
        print(f"\nLetter Sequence Analysis:")
        all_letters = []
        for cube_id in sorted(self.cube_updates.keys()):
            letters = [update[1] for update in self.cube_updates[cube_id]]
            all_letters.extend(letters)
            print(f"  Cube {cube_id} sequence: {' '.join(letters[:10])}{'...' if len(letters) > 10 else ''}")
            
        # Check for expected pattern (A-Z repeating)
        if all_letters:
            expected_pattern = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            pattern_matches = 0
            for i, letter in enumerate(all_letters):
                expected = expected_pattern[i % 26]
                if letter == expected:
                    pattern_matches += 1
                    
            print(f"  Pattern matching: {pattern_matches}/{len(all_letters)} ({pattern_matches/len(all_letters)*100:.1f}%)")

def run_concurrent_random_letters():
    """Run random_letters.sh in the background for testing"""
    print("Starting random_letters.sh process...")
    
    try:
        process = subprocess.Popen(
            ["./random_letters.sh"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return process
    except Exception as e:
        print(f"Failed to start random_letters.sh: {e}")
        return None

async def main():
    # Ask user if they want to auto-start random_letters.sh
    response = input("Auto-start random_letters.sh? (y/n): ").lower().strip()
    
    test = RandomLettersTest()
    
    def signal_handler(sig, frame):
        print("\nShutting down...")
        test.running = False
        
    signal.signal(signal.SIGINT, signal_handler)
    
    process = None
    if response == 'y':
        process = run_concurrent_random_letters()
        if process:
            print("Started random_letters.sh")
        else:
            print("Failed to start random_letters.sh - run it manually")
    
    try:
        await test.run_test(duration_seconds=30)
    finally:
        if process:
            print("Terminating random_letters.sh...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

if __name__ == "__main__":
    asyncio.run(main())