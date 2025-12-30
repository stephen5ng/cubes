#!/usr/bin/env python3
"""
Test script for MQTT migration strategies

Run this to test different retained message strategies and measure their impact.
"""

import asyncio
import argparse
import time
import json
import logging
from typing import Dict, Any

from monitoring.mqtt_metrics import mqtt_metrics, MqttMetricsLogger
from non_retained_mqtt import NonRetainedMqttManager, MIGRATION_STRATEGIES, migrate_to_non_retained

async def run_migration_test(strategy_name: str, duration_seconds: int = 60):
    """
    Test a specific migration strategy for a given duration.
    
    Args:
        strategy_name: One of the keys from MIGRATION_STRATEGIES
        duration_seconds: How long to run the test
    """
    
    if strategy_name not in MIGRATION_STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(MIGRATION_STRATEGIES.keys())}")
    
    strategy = MIGRATION_STRATEGIES[strategy_name]
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create a test publish queue
    publish_queue = asyncio.Queue()
    
    # Set up metrics
    metrics_logger = MqttMetricsLogger(mqtt_metrics, f"mqtt_metrics_{strategy_name}.jsonl")
    
    print(f"Starting migration test: {strategy_name}")
    print(f"Strategy: {strategy}")
    print(f"Duration: {duration_seconds} seconds")
    print(f"Metrics will be logged to: mqtt_metrics_{strategy_name}.jsonl")
    
    # Start metrics logging
    metrics_task = asyncio.create_task(metrics_logger.start_logging())
    
    try:
        # Apply migration strategy
        non_retained_manager = await migrate_to_non_retained(publish_queue, None, strategy)
        
        # Start non-retained manager services
        service_tasks = await non_retained_manager.start_services()
        
        # Simulate typical game traffic
        await simulate_game_traffic(publish_queue, non_retained_manager, duration_seconds)
        
        # Get final metrics
        final_stats = mqtt_metrics.get_stats()
        strategy_stats = non_retained_manager.get_strategy_stats()
        
        print("\\n=== Test Results ===")
        print(f"Strategy: {strategy_name}")
        print(f"Messages published: {final_stats['messages']['published_total']}")
        print(f"Retained messages: {final_stats['messages']['published_retained']}")
        print(f"Retention rate: {final_stats['messages']['retention_rate']:.1%}")
        print(f"Max queue size: {final_stats['queue']['max_size']}")
        print(f"Average latency p95: {final_stats['latency_ms']['roundtrip_p95']:.1f}ms")
        
        print("\\nStrategy-specific stats:")
        print(json.dumps(strategy_stats, indent=2))
        
        # Save results
        results = {
            "strategy": strategy_name,
            "duration_s": duration_seconds,
            "mqtt_stats": final_stats,
            "strategy_stats": strategy_stats
        }
        
        with open(f"test_results_{strategy_name}.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\\nResults saved to: test_results_{strategy_name}.json")
        
    finally:
        # Clean up
        metrics_logger.stop_logging()
        await metrics_task
        
        for task in service_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

async def simulate_game_traffic(publish_queue: asyncio.Queue, non_retained_manager: NonRetainedMqttManager, duration_seconds: int):
    """Simulate typical game MQTT traffic patterns"""
    
    start_time = time.time()
    cube_ids = [str(i) for i in range(1, 13)]  # 12 cubes
    letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
    
    print("Simulating game traffic...")
    
    message_count = 0
    
    while time.time() - start_time < duration_seconds:
        now_ms = time.time() * 1000
        
        # Simulate different types of messages
        
        # 1. Letter changes (frequent during letter selection)
        for i, cube_id in enumerate(cube_ids):
            if message_count % 10 == i % 10:  # Stagger updates
                letter = letters[i % len(letters)]
                await non_retained_manager.set_cube_letter(cube_id, letter, now_ms)
        
        # 2. Border updates (frequent during word formation)
        if message_count % 5 == 0:
            for cube_id in cube_ids[:6]:  # First 6 cubes
                color = "0xFFFF" if (message_count // 5) % 2 == 0 else None
                await non_retained_manager.set_cube_border(cube_id, "top", color, now_ms)
                await non_retained_manager.set_cube_border(cube_id, "bottom", color, now_ms)
        
        # 3. Lock updates (less frequent)
        if message_count % 20 == 0:
            cube_id = cube_ids[message_count % len(cube_ids)]
            locked = (message_count // 20) % 2 == 0
            await non_retained_manager.set_cube_lock(cube_id, locked, now_ms)
        
        # 4. NFC tag reads (simulate cube interactions)
        if message_count % 7 == 0:
            sender = str((message_count // 7) % 12 + 1)
            tag_data = f"tag_{message_count}"
            await publish_queue.put((f"game/nfc/{sender}", tag_data, True, now_ms))
        
        # 5. Flash messages (always non-retained)
        if message_count % 15 == 0:
            cube_id = cube_ids[message_count % len(cube_ids)]
            await publish_queue.put((f"cube/{cube_id}/flash", "1", False, now_ms))
        
        message_count += 1
        
        # Variable delay to simulate real traffic patterns
        delay = 0.1 + (message_count % 3) * 0.05  # 0.1-0.2s delays
        await asyncio.sleep(delay)
    
    print(f"Simulation complete. Generated {message_count} messages.")

async def compare_all_strategies(duration_seconds: int = 30):
    """Run tests for all migration strategies and compare results"""
    
    results = {}
    
    for strategy_name in MIGRATION_STRATEGIES.keys():
        print(f"\\n{'='*50}")
        print(f"Testing strategy: {strategy_name}")
        print(f"{'='*50}")
        
        # Reset metrics for each test
        global mqtt_metrics
        from monitoring.mqtt_metrics import MqttMetrics
        mqtt_metrics = MqttMetrics()
        
        try:
            await run_migration_test(strategy_name, duration_seconds)
            
            # Load results
            with open(f"test_results_{strategy_name}.json", "r") as f:
                results[strategy_name] = json.load(f)
                
        except Exception as e:
            print(f"Error testing {strategy_name}: {e}")
            results[strategy_name] = {"error": str(e)}
    
    # Generate comparison report
    print(f"\\n{'='*60}")
    print("STRATEGY COMPARISON REPORT")
    print(f"{'='*60}")
    
    print(f"{'Strategy':<15} {'Retention%':<12} {'Msgs':<8} {'MaxQueue':<10} {'P95Lat(ms)':<12}")
    print("-" * 60)
    
    for strategy_name, result in results.items():
        if "error" in result:
            print(f"{strategy_name:<15} ERROR: {result['error']}")
            continue
            
        stats = result["mqtt_stats"]
        retention_pct = stats["messages"]["retention_rate"] * 100
        total_msgs = stats["messages"]["published_total"]
        max_queue = stats["queue"]["max_size"]
        p95_latency = stats["latency_ms"]["roundtrip_p95"]
        
        print(f"{strategy_name:<15} {retention_pct:<11.1f}% {total_msgs:<8} {max_queue:<10} {p95_latency:<12.1f}")
    
    # Save comparison
    with open("strategy_comparison.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\\nDetailed comparison saved to: strategy_comparison.json")

def main():
    parser = argparse.ArgumentParser(description="Test MQTT migration strategies")
    parser.add_argument("--strategy", choices=list(MIGRATION_STRATEGIES.keys()), 
                        help="Test a specific strategy")
    parser.add_argument("--compare", action="store_true",
                        help="Compare all strategies")
    parser.add_argument("--duration", type=int, default=60,
                        help="Test duration in seconds (default: 60)")
    
    args = parser.parse_args()
    
    if args.compare:
        asyncio.run(compare_all_strategies(args.duration))
    elif args.strategy:
        asyncio.run(run_migration_test(args.strategy, args.duration))
    else:
        print("Use --strategy <name> to test a specific strategy, or --compare to test all")
        print(f"Available strategies: {list(MIGRATION_STRATEGIES.keys())}")

if __name__ == "__main__":
    main()