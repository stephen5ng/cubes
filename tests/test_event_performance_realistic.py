#!/usr/bin/env python3

import asyncio
import time
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the modified event system
from utils import pygameasync

async def test_event_system():
    """Test the queue-based event system with realistic patterns"""
    print("Testing queue-based event system...")
    
    # Register multiple event handlers like in the real game
    @pygameasync.events.on("game.stage_guess")
    async def stage_guess(score, guess, player, now_ms):
        await asyncio.sleep(0.0001)  # Very small work
    
    @pygameasync.events.on("game.old_guess")
    async def old_guess(guess, player, now_ms):
        await asyncio.sleep(0.0001)
    
    @pygameasync.events.on("rack.update_rack")
    async def update_rack(tiles, highlight_length, guess_length, player, now_ms):
        await asyncio.sleep(0.0001)
    
    @pygameasync.events.on("input.update_previous_guesses")
    async def update_previous_guesses(previous_guesses, now_ms):
        await asyncio.sleep(0.0001)
    
    # Start the event engine
    await pygameasync.events.start()
    
    # Start timing
    start_time = time.time()
    start_tasks = len(asyncio.all_tasks())
    
    # Simulate realistic event patterns (like in the game)
    for i in range(1000):
        # Simulate game events
        pygameasync.events.trigger("game.stage_guess", 100, f"word_{i}", 0, i * 100)
        pygameasync.events.trigger("rack.update_rack", [], 0, 0, 0, i * 100)
        pygameasync.events.trigger("input.update_previous_guesses", [f"word_{i}"], i * 100)
        
        if i % 10 == 0:  # Every 10th event
            pygameasync.events.trigger("game.old_guess", f"old_word_{i}", 0, i * 100)
    
    # Wait for processing to complete
    await asyncio.sleep(1)
    
    end_time = time.time()
    end_tasks = len(asyncio.all_tasks())
    
    # Stop the event engine
    await pygameasync.events.stop()
    
    print(f"Queue system: {end_time - start_time:.3f} seconds")
    print(f"Tasks created: {end_tasks - start_tasks}")

async def test_memory_usage():
    """Test memory usage by monitoring task creation during event bursts"""
    print("\nTesting memory usage during event bursts...")
    
    # Test queue system
    print("Queue system - burst of 100 events...")
    await pygameasync.events.start()
    
    @pygameasync.events.on("burst.test")
    async def handler(data):
        pass
    
    start_tasks = len(asyncio.all_tasks())
    
    # Create burst of events
    for i in range(100):
        pygameasync.events.trigger("burst.test", f"data_{i}")
    
    # Check immediately after burst
    immediate_tasks = len(asyncio.all_tasks())
    print(f"Tasks immediately after burst: {immediate_tasks - start_tasks}")
    
    # Wait and check again
    await asyncio.sleep(0.1)
    end_tasks = len(asyncio.all_tasks())
    print(f"Tasks after waiting: {end_tasks - start_tasks}")
    
    await pygameasync.events.stop()

async def main():
    print("Simplified Queue-Based Event System Performance Test")
    print("=" * 60)
    
    # Test memory usage
    await test_memory_usage()
    
    # Test performance with realistic patterns
    await test_event_system()
    
    print("\nTest completed!")

if __name__ == "__main__":
    asyncio.run(main()) 