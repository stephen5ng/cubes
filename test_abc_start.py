#!/usr/bin/env python3
"""
Test script for ABC start sequence functionality.
"""

import sys
import time
import asyncio
from unittest.mock import AsyncMock
sys.path.append('.')

import cubes_to_game

class MockTopic:
    def __init__(self, topic_str):
        self.value = topic_str

async def test_abc_start_sequence():
    print("Testing ABC start sequence functionality...")
    
    # Mock a publish queue
    publish_queue = AsyncMock()
    
    # Mock the start game callback
    start_game_mock = AsyncMock()
    cubes_to_game.set_start_game_callback(start_game_mock)
    
    # Reset the system state
    cubes_to_game._abc_start_active = False
    cubes_to_game._abc_cubes = {"A": None, "B": None, "C": None}
    cubes_to_game._game_running = False
    cubes_to_game._last_game_end_time_ms = 0
    
    # Set up mock cube managers with some cubes
    cubes_to_game.cube_managers = []
    manager = cubes_to_game.CubeManager(0)
    # Direct cube IDs only in new protocol
    manager.cube_list = ["cube1", "cube2", "cube3", "cube4", "cube5"]
    manager.cube_chain = {}  # No connections initially
    cubes_to_game.cube_managers = [manager]
    
    current_time = int(time.time() * 1000)
    
    # First, simulate all cubes reporting "-" (no adjacencies) - required for new protocol
    all_cubes = ["cube1", "cube2", "cube3", "cube4", "cube5"]
    for cube_id in all_cubes:
        message = MockTopic(f"cube/right/{cube_id}")
        # Simulate reporting no neighbor
        await cubes_to_game.handle_mqtt_message(publish_queue, type('Message', (), {
            'topic': message,
            'payload': b'-'
        })(), current_time)
    
    # Test 1: Activate ABC sequence when no moratorium
    await cubes_to_game.activate_abc_start_if_ready(publish_queue, current_time)
    assert cubes_to_game._abc_start_active, "ABC sequence should be active"
    assert all(cubes_to_game._abc_cubes.values()), "All ABC cubes should be assigned"
    print("✓ Test 1 passed: ABC sequence activated at startup")
    
    # Test 2: Check that the cubes are assigned properly
    assert cubes_to_game._abc_cubes["A"] != cubes_to_game._abc_cubes["B"], "A and B should be different cubes"
    assert cubes_to_game._abc_cubes["B"] != cubes_to_game._abc_cubes["C"], "B and C should be different cubes"
    assert cubes_to_game._abc_cubes["A"] != cubes_to_game._abc_cubes["C"], "A and C should be different cubes"
    print("✓ Test 2 passed: ABC cubes are properly assigned to different cubes")
    
    # Test 3: Simulate connecting A->B->C and check if sequence is detected
    cube_a = cubes_to_game._abc_cubes["A"]
    cube_b = cubes_to_game._abc_cubes["B"]
    cube_c = cubes_to_game._abc_cubes["C"]
    
    # Create A->B chain
    manager.cube_chain[cube_a] = cube_b
    # Create B->C chain  
    manager.cube_chain[cube_b] = cube_c
    
    sequence_complete = await cubes_to_game._check_abc_sequence_complete()
    assert sequence_complete, "ABC sequence should be detected as complete"
    print("✓ Test 3 passed: ABC sequence correctly detected when cubes are connected A->B->C")
    
    # Test 4: Clear sequence and verify it's cleared
    cubes_to_game._clear_abc_start_sequence()
    assert not cubes_to_game._abc_start_active, "ABC sequence should be cleared"
    assert all(cube is None for cube in cubes_to_game._abc_cubes.values()), "All ABC cube assignments should be cleared"
    print("✓ Test 4 passed: ABC sequence properly cleared")
    
    # Test 5: Test moratorium blocking
    cubes_to_game._last_game_end_time_ms = current_time
    cubes_to_game.CUBE_START_MORATORIUM_MS = 1000  # 1 second for testing
    
    # Should not activate during moratorium
    await cubes_to_game.activate_abc_start_if_ready(publish_queue, current_time + 500)
    assert not cubes_to_game._abc_start_active, "ABC sequence should not activate during moratorium"
    print("✓ Test 5 passed: ABC sequence correctly blocked during moratorium")
    
    # Should activate after moratorium (but need to report status again since it was cleared)
    # Also clear the cube chain to avoid interference from previous tests
    manager.cube_chain = {}
    
    for cube_id in all_cubes:
        msg = MockTopic(f"cube/right/{cube_id}")
        await cubes_to_game.handle_mqtt_message(publish_queue, type('Message', (), {
            'topic': msg,
            'payload': b'-'
        })(), current_time + 1500)
    
    await cubes_to_game.activate_abc_start_if_ready(publish_queue, current_time + 1500) 
    assert cubes_to_game._abc_start_active, "ABC sequence should activate after moratorium"
    print("✓ Test 6 passed: ABC sequence activated after moratorium expires")
    
    # Test 7: Test non-touching cube selection
    cubes_to_game._clear_abc_start_sequence()
    
    # Report status with adjacency: cube1->cube2 
    # cube1 -> cube2
    msg1 = MockTopic("cube/right/cube1")
    await cubes_to_game.handle_mqtt_message(publish_queue, type('Message', (), {
        'topic': msg1,
        'payload': b'cube2'
    })(), current_time)
    
    for cube_id in ["cube2", "cube3", "cube4", "cube5"]:
        msg = MockTopic(f"cube/right/{cube_id}")
        await cubes_to_game.handle_mqtt_message(publish_queue, type('Message', (), {
            'topic': msg,
            'payload': b'-'
        })(), current_time)
    
    selected_cubes = await cubes_to_game._find_non_touching_cubes(publish_queue, current_time)
    # cube1 and cube2 are connected, so they shouldn't both be selected
    # The function should pick 3 cubes that aren't directly connected to each other
    assert len(selected_cubes) == 3, "Should select exactly 3 cubes"
    
    # Verify no selected cube is directly connected to another selected cube using reports
    # Build adjacency from managers directly since helper removed
    edges = set()
    for mgr in cubes_to_game.cube_managers:
        for src, dst in mgr.cube_chain.items():
            edges.add((src, dst)); edges.add((dst, src))
    connected_pairs = 0
    for i, cube_a in enumerate(selected_cubes):
        for j, cube_b in enumerate(selected_cubes):
            if i != j and ((cube_a, cube_b) in edges or (cube_b, cube_a) in edges):
                connected_pairs += 1
    
    assert connected_pairs == 0, "Selected cubes should not be directly connected to each other"
    print("✓ Test 7 passed: Non-touching cube selection works correctly")
    
    # Test 8: Test new "-" protocol
    print("✓ Starting \"-\" protocol tests...")
    
    # Clear everything and test "-"-based adjacency detection
    cubes_to_game._clear_abc_start_sequence()
    
    # All cubes report "-" initially (no adjacencies)
    all_cubes = ["cube1", "cube2", "cube3", "cube4", "cube5"]
    for cube_id in all_cubes:
        msg = MockTopic(f"cube/right/{cube_id}")
        await cubes_to_game.handle_mqtt_message(publish_queue, type('Message', (), {
            'topic': msg,
            'payload': b'-'
        })(), current_time)
    
    # Should have all cubes reported
    assert cubes_to_game._all_cubes_reported, "All cubes should be marked as reported"
    print("✓ Test 8a passed: All cubes reported \"-\" status")
    
    # ABC should now activate since we have complete info
    await cubes_to_game.activate_abc_start_if_ready(publish_queue, current_time)
    assert cubes_to_game._abc_start_active, "ABC should activate after all cubes report"
    print("✓ Test 8b passed: ABC activated after complete status reports")
    
    # Test adjacency detection with "-" protocol
    cubes_to_game._clear_abc_start_sequence()
    
    # Simulate some adjacencies
    # cube1 adjacent to cube2; others free
    msg1 = MockTopic("cube/right/cube1")
    await cubes_to_game.handle_mqtt_message(publish_queue, type('Message', (), {
        'topic': msg1,
        'payload': b'cube2'
    })(), current_time)
    msg2 = MockTopic("cube/right/cube2")
    await cubes_to_game.handle_mqtt_message(publish_queue, type('Message', (), {
        'topic': msg2,
        'payload': b'-'
    })(), current_time)
    for cube_id in ["cube3", "cube4", "cube5"]:
        msg = MockTopic(f"cube/right/{cube_id}")
        await cubes_to_game.handle_mqtt_message(publish_queue, type('Message', (), {
            'topic': msg,
            'payload': b'-'
        })(), current_time)
    # Validate adjacency from chain
    assert manager.cube_chain.get("cube1") == "cube2", "cube1 should be adjacent to cube2"
    print("✓ Test 8c passed: Adjacency correctly detected from status reports")
    
    print("\n🎉 All ABC start sequence tests passed!")

if __name__ == "__main__":
    asyncio.run(test_abc_start_sequence())