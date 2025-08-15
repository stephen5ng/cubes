#!/usr/bin/env python3
"""Test that ABC start waits for all cube neighbor reports."""

import asyncio
import sys
sys.path.append('.')
import cubes_to_game
from unittest.mock import Mock

class MockTopic:
    def __init__(self, value):
        self.value = value

async def test_abc_neighbor_reporting():
    """Test that ABC start waits for neighbor reports from all cubes."""
    
    # Reset state
    cubes_to_game._abc_start_active = False
    cubes_to_game._abc_cubes = {"A": None, "B": None, "C": None}
    cubes_to_game._game_running = False
    cubes_to_game._last_game_end_time_ms = 0
    
    # Set up mock cube managers with 3 cubes each
    cubes_to_game.cube_managers = []
    
    # Create mock cube manager for player 0
    manager = cubes_to_game.CubeManager(0)
    manager.cube_list = ["cube1", "cube2", "cube3"]
    cubes_to_game.cube_managers.append(manager)
    
    # Create async mock for publish queue
    class MockQueue:
        async def put(self, item):
            pass
    
    publish_queue = MockQueue()
    current_time = 1000
    
    # Test 1: No neighbor reports yet - ABC should not activate
    await cubes_to_game.activate_abc_start_if_ready(publish_queue, current_time)
    assert not cubes_to_game._abc_start_active, "ABC should not activate without neighbor reports"
    print("✓ Test 1 passed: ABC does not activate without neighbor reports")
    
    # Test 2: Partial neighbor reports - ABC should not activate
    manager.cubes_to_neighbors["cube1"] = "-"
    manager.cubes_to_neighbors["cube2"] = "-"
    # cube3 hasn't reported yet
    
    await cubes_to_game.activate_abc_start_if_ready(publish_queue, current_time)
    assert not cubes_to_game._abc_start_active, "ABC should not activate with partial neighbor reports"
    print("✓ Test 2 passed: ABC does not activate with partial neighbor reports")
    
    # Test 3: All cubes report - ABC should activate
    manager.cubes_to_neighbors["cube3"] = "-"
    
    await cubes_to_game.activate_abc_start_if_ready(publish_queue, current_time)
    assert cubes_to_game._abc_start_active, "ABC should activate when all cubes have reported"
    print("✓ Test 3 passed: ABC activates when all cubes have reported")
    
    # Test 4: Test _all_cubes_have_reported_neighbors function directly
    cubes_to_game._abc_start_active = False
    manager.cubes_to_neighbors = {}  # Clear reports
    
    assert not cubes_to_game._all_cubes_have_reported_neighbors(), "Should return False when no reports"
    
    # Add all reports
    manager.cubes_to_neighbors = {
        "cube1": "cube2",  # cube1 sees cube2
        "cube2": "-",     # cube2 sees nothing  
        "cube3": "cube1"   # cube3 sees cube1
    }
    
    assert cubes_to_game._all_cubes_have_reported_neighbors(), "Should return True when all cubes have reported"
    print("✓ Test 4 passed: _all_cubes_have_reported_neighbors works correctly")
    
    print("🎉 All ABC neighbor reporting tests passed!")

if __name__ == "__main__":
    asyncio.run(test_abc_neighbor_reporting())