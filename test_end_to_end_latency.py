#!/usr/bin/env python3

"""Test the end-to-end latency measurement system with mock data."""

import json
import os
import time
from src.logging.latency_logger import LatencyLogger

def create_test_data():
    """Create test latency data and mock ESP32 serial output."""
    
    # Create test latency logger
    test_logger = LatencyLogger("test_latency_e2e.jsonl", True)
    
    print("Creating test end-to-end measurements...")
    
    # Simulate 3 letter updates with correlation IDs
    test_correlations = []
    
    for i, letter in enumerate(['A', 'B', 'C']):
        correlation_id = f"test-corr-{i}-{int(time.time()*1000)}"
        cube_id = str(i + 1)
        
        # Log game server start
        test_logger.log_roundtrip_latency(
            "game_server",
            cube_id,
            0.0,
            f"letter_start_{correlation_id}_{letter}"
        )
        
        test_correlations.append((correlation_id, cube_id, letter))
        print(f"  Game server logged letter '{letter}' to cube {cube_id}")
    
    # Create mock ESP32 serial output
    with open("test_esp32_serial.log", "w") as f:
        base_time = int(time.time() * 1000) % (2**32)  # ESP32 millis() format
        
        for i, (correlation_id, cube_id, letter) in enumerate(test_correlations):
            # Simulate various latencies: 45ms, 120ms, 280ms
            latencies = [45, 120, 280]
            esp32_time = base_time + (i * 1000) + latencies[i]  
            
            f.write(f"[{esp32_time}] MQTT message received - Topic: letter, Payload: {letter}\n")
            f.write(f"[{esp32_time + latencies[i]}] DISPLAY_BUFFER_FLIP - correlation_id: {correlation_id}\n")
            print(f"  ESP32 logged display flip for '{letter}' after {latencies[i]}ms")
    
    print("✓ Test data created")
    return test_correlations


def test_analysis():
    """Test the correlation analysis."""
    print("\nTesting latency analysis...")
    
    # Run the analysis script
    import subprocess
    result = subprocess.run([
        "cube_env/bin/python", "analyze_latency.py",
        "--latency-log", "test_latency_e2e.jsonl", 
        "--esp32-serial", "test_esp32_serial.log",
        "--output", "test_results.csv"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("Analysis output:")
        print(result.stdout)
        
        # Show CSV results if created
        if os.path.exists("test_results.csv"):
            print("\nDetailed results:")
            with open("test_results.csv", "r") as f:
                print(f.read())
    else:
        print(f"Analysis failed: {result.stderr}")


def cleanup():
    """Clean up test files."""
    test_files = [
        "test_latency_e2e.jsonl",
        "test_esp32_serial.log", 
        "test_results.csv"
    ]
    
    for file in test_files:
        if os.path.exists(file):
            os.remove(file)
    
    print("\n✓ Test files cleaned up")


def main():
    print("=== End-to-End Latency Measurement Test ===")
    
    try:
        correlations = create_test_data()
        test_analysis()
    finally:
        cleanup()
    
    print("\n=== Test Complete ===")
    print("To use with real game:")
    print("1. Set LATENCY_LOGGING_ENABLED=true")
    print("2. Run game server (creates latency_metrics.jsonl)")
    print("3. Capture ESP32 serial output to file")
    print("4. Run: python analyze_latency.py --esp32-serial <serial_file>")


if __name__ == "__main__":
    main()