#!/usr/bin/env python3

"""Simple test script to verify LatencyLogger functionality."""

import os
import time
from src.logging.latency_logger import LatencyLogger

def test_latency_logger():
    # Create a test logger
    test_logger = LatencyLogger("test_latency.jsonl", True)
    
    print("Testing LatencyLogger...")
    
    # Test 1: Basic operation timing
    token = test_logger.start_operation("test_operation")
    time.sleep(0.01)  # Simulate 10ms operation
    test_logger.end_operation(token, True)
    
    # Test 2: MQTT publish logging
    test_logger.log_mqtt_publish("cube/1/letter", 1, 5.5, True)
    
    # Test 3: Event processing logging
    test_logger.log_event_processing("input_movement", 2.3)
    
    # Test 4: Input latency logging
    test_logger.log_input_latency("keyboard", "player_0", 1.2)
    
    # Test 5: Roundtrip latency logging
    test_logger.log_roundtrip_latency("game_server", "cube_1", 15.8, "letter_update")
    
    print("✓ All latency logging calls completed")
    print("Check test_latency.jsonl for output")
    
    # Clean up
    if os.path.exists("test_latency.jsonl"):
        with open("test_latency.jsonl", 'r') as f:
            lines = f.readlines()
            print(f"✓ Created {len(lines)} log entries")
            for i, line in enumerate(lines[:2]):  # Show first 2 entries
                print(f"  Entry {i+1}: {line.strip()}")
        
        # Clean up test file
        os.remove("test_latency.jsonl")
        print("✓ Test file cleaned up")

if __name__ == "__main__":
    test_latency_logger()