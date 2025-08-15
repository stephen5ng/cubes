#!/usr/bin/env python3
"""
Test script for the cube start moratorium functionality.
"""

import sys
import time
sys.path.append('.')

import cubes_to_game

def test_moratorium():
    print("Testing cube start moratorium functionality...")
    
    # Set a short moratorium for testing (2 seconds)
    cubes_to_game.CUBE_START_MORATORIUM_MS = 2000
    
    # Test 1: No previous game end should allow start
    current_time = int(time.time() * 1000)
    assert cubes_to_game._is_cube_start_allowed(current_time), "Should allow start when no previous game end"
    print("✓ Test 1 passed: Start allowed when no previous game end")
    
    # Test 2: Just after game end should block start
    cubes_to_game.set_game_end_time(current_time)
    assert not cubes_to_game._is_cube_start_allowed(current_time + 100), "Should block start immediately after game end"
    print("✓ Test 2 passed: Start blocked immediately after game end")
    
    # Test 3: Just before moratorium expires should still block
    assert not cubes_to_game._is_cube_start_allowed(current_time + 1999), "Should still block just before moratorium expires"
    print("✓ Test 3 passed: Start still blocked just before moratorium expires")
    
    # Test 4: After moratorium expires should allow start
    assert cubes_to_game._is_cube_start_allowed(current_time + 2000), "Should allow start after moratorium expires"
    print("✓ Test 4 passed: Start allowed after moratorium expires")
    
    # Test 5: Well after moratorium expires should allow start
    assert cubes_to_game._is_cube_start_allowed(current_time + 5000), "Should allow start well after moratorium expires"
    print("✓ Test 5 passed: Start allowed well after moratorium expires")
    
    print("\n🎉 All tests passed! Moratorium functionality working correctly.")

if __name__ == "__main__":
    test_moratorium()