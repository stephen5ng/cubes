#!/usr/bin/env python3
"""
Cube Responsiveness Test

Runs a functional test then measures cube responsiveness to detect
post-test message backlog processing. Useful for validating MQTT
performance improvements.

Usage:
    ./test_cube_responsiveness.py sng          # Quick test
    ./test_cube_responsiveness.py stress_0.1   # Medium test  
    ./test_cube_responsiveness.py stress_0.01  # Long test
"""

import asyncio
import subprocess
import sys
import os
import time
from post_test_ping_monitor import CubePingMonitor

def run_functional_test(test_name):
    """Run functional test with real broker"""
    print(f"🧪 Running functional test: {test_name}")
    print("=" * 60)
    
    # Set up environment for real broker
    env = os.environ.copy()
    env['MQTT_SERVER'] = '192.168.8.247'
    
    # Run the test
    cmd = ["./runpygame.sh", "--replay", f"replay/{test_name}/game_replay.jsonl"]
    
    start_time = time.time()
    try:
        result = subprocess.run(cmd, env=env, capture_output=False, text=True)
        duration = time.time() - start_time
        
        print(f"\n✅ Test completed in {duration:.1f}s with return code: {result.returncode}")
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def measure_cube_responsiveness(cube_id="1", monitor_duration=60, ping_interval=2):
    """Measure how quickly cube becomes responsive after test"""
    print(f"\n🔍 Measuring cube {cube_id} responsiveness")
    print("=" * 60)
    
    monitor = CubePingMonitor(broker="192.168.8.247", cube_id=cube_id)
    await monitor.monitor_post_test_activity(
        duration_seconds=monitor_duration,
        ping_interval=ping_interval
    )

def analyze_results():
    """Analyze the ping results and provide recommendations"""
    import json
    
    try:
        with open('post_test_ping_results.json', 'r') as f:
            data = json.load(f)
            
        summary = data['summary']
        results = data['results']
        
        print(f"\n🎯 RESPONSIVENESS TEST RESULTS")
        print("=" * 60)
        
        if summary['responses_received'] == 0:
            print("❌ FAIL: Cube completely unresponsive")
            print("   Recommendation: Investigate MQTT broker overload")
            return False
            
        avg_response = summary['avg_response_ms']
        response_rate = summary['response_rate_percent']
        max_response = summary['max_response_ms']
        
        # Calculate recovery metrics if we have enough data
        recovery_time = None
        if len(results) >= 5:
            # Find when response times drop below 1000ms consistently
            for i, result in enumerate(results):
                if result['response_time_ms'] < 1000:
                    # Check if next few responses are also fast
                    next_responses = results[i:i+3]
                    if len(next_responses) >= 3 and all(r['response_time_ms'] < 1000 for r in next_responses):
                        recovery_time = result['receive_time'] - results[0]['receive_time']
                        break
        
        print(f"Response Rate: {response_rate:.1f}%")
        print(f"Average Response: {avg_response:.1f}ms")
        print(f"Max Response: {max_response:.1f}ms")
        if recovery_time:
            print(f"Recovery Time: {recovery_time:.1f}s")
        
        # Grade the performance
        if response_rate < 50:
            grade = "❌ CRITICAL"
            recommendation = "Cube severely overloaded - immediate attention needed"
        elif avg_response > 5000:
            grade = "🔴 POOR" 
            recommendation = "High latency indicates significant message backlog"
        elif avg_response > 1000:
            grade = "🟡 FAIR"
            recommendation = "Moderate backlog - room for improvement"
        elif avg_response > 500:
            grade = "🟢 GOOD"
            recommendation = "Acceptable performance with minor delays"
        else:
            grade = "✅ EXCELLENT"
            recommendation = "Minimal latency - optimal performance"
            
        print(f"\nGrade: {grade}")
        print(f"Assessment: {recommendation}")
        
        return avg_response < 1000 and response_rate > 80
        
    except FileNotFoundError:
        print("❌ No ping results found")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: ./test_cube_responsiveness.py <test_name>")
        print("Examples:")
        print("  ./test_cube_responsiveness.py sng")
        print("  ./test_cube_responsiveness.py stress_0.1")
        sys.exit(1)
    
    test_name = sys.argv[1]
    
    print(f"🚀 CUBE RESPONSIVENESS TEST")
    print(f"Test: {test_name}")
    print(f"Broker: 192.168.8.247")
    print("=" * 60)
    
    # Step 1: Run functional test
    test_success = run_functional_test(test_name)
    if not test_success:
        print("❌ Functional test failed - aborting responsiveness test")
        sys.exit(1)
    
    # Step 2: Measure responsiveness  
    print(f"\n⏱️  Starting responsiveness measurement in 3 seconds...")
    time.sleep(3)  # Brief pause to ensure test cleanup
    
    # Adjust monitoring parameters based on test type
    if test_name == "sng":
        duration = 30  # Short test, expect quick recovery
        interval = 1
    elif "stress" in test_name:
        duration = 90   # Stress tests may have longer backlogs
        interval = 2
    else:
        duration = 45   # Default
        interval = 1
    
    try:
        asyncio.run(measure_cube_responsiveness(
            monitor_duration=duration,
            ping_interval=interval
        ))
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1)
    
    # Step 3: Analyze and grade results
    success = analyze_results()
    
    # Step 4: Summary
    print(f"\n📊 FINAL SUMMARY")
    print("=" * 60)
    if success:
        print("✅ PASS: Cube responsiveness within acceptable limits")
        sys.exit(0) 
    else:
        print("❌ FAIL: Cube responsiveness below acceptable thresholds")
        print("Consider MQTT performance optimizations")
        sys.exit(1)

if __name__ == "__main__":
    main()