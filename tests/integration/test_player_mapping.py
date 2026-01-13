
import pytest
import asyncio
from unittest.mock import patch, MagicMock

from config import game_config
from hardware import cubes_to_game
from hardware import cubes_interface
from tests.fixtures.game_factory import create_test_game, async_test

@async_test
async def test_default_mapping_keyboard_mode():
    """Verify default mapping when no cube sets have started (keyboard mode)."""
    # 1. Setup game with 1 player (default)
    game, mqtt, queue = await create_test_game(player_count=1)
    
    # 2. Ensure NO cube sets are started (simulate keyboard/default start)
    cubes_to_game.reset_started_cube_sets()
    
    # 3. Start the game
    # We need to simulate the "start game" signal that usually comes from ABC completion or keyboard
    # For keyboard/default, we just call app.start directly
    current_time = 1000
    await game._app.start(current_time)
    
    # 4. Verify Mapping
    # Logic: If no hardware started, P0 -> Set 0, P1 -> Set 1, but only P0 is "started" in hardware to receive updates
    
    # Check internal mapping
    # Check internal mapping
    assert game._app.get_all_player_mappings() == {0: 0, 1: 1}
    
    # Check hardware "started players" status
    # In default mode, only Player 0 should be marked as started
    assert game._app.hardware.has_player_started_game(0) is True
    assert game._app.hardware.has_player_started_game(1) is False

@async_test
async def test_mapping_p0_cube_set_0():
    """Verify mapping when only Cube Set 0 completes ABC."""
    game, mqtt, queue = await create_test_game(player_count=1)
    
    # Simulate Cube Set 0 completing ABC
    cubes_to_game.reset_started_cube_sets()
    cubes_to_game.add_started_cube_set(0)
    
    current_time = 1000
    await game._app.start(current_time)
    
    # Verify Mapping: P0 -> Set 0 (since it's the only one)
    # The calculate_player_mapping returns {0: 0} when only [0] is started
    # BUT App.py updates the default mapping with the result.
    # So {0:0, 1:1}.update({0:0}) -> {0:0, 1:1} effectively
    # Wait, check logic:
    # if len(started) == 1: returns {sid: sid} -> {0: 0}
    # update({0:0}) -> No change effectively to P0, P1 remains 1.
    
    assert game._app.get_player_cube_set_mapping(0) == 0
    
    # Verify Hardware State
    assert game._app.hardware.has_player_started_game(0) is True
    assert game._app.hardware.has_player_started_game(1) is False

@async_test
async def test_mapping_p1_cube_set_1():
    """Verify mapping when only Cube Set 1 completes ABC (Single player on right)."""
    game, mqtt, queue = await create_test_game(player_count=1)
    
    # Simulate Cube Set 1 completing ABC
    cubes_to_game.reset_started_cube_sets()
    cubes_to_game.add_started_cube_set(1)
    
    current_time = 1000
    await game._app.start(current_time)
    
    # Verify Mapping
    # calculate_player_mapping([1]) -> {1: 1}
    # App mapping update: {0:0, 1:1}.update({1:1}) -> {0:0, 1:1}
    # Wait, the KEY is the logical player ID. 
    # If calculate_player_mapping returns {1: 1}, it means Logical Player 1 is using Cube Set 1.
    # BUT, if I am playing single player on the right, am I Logical Player 0 or 1?
    # App._player_count starts at 1.
    # If the mapping says P1->S1, then P0 has no mapping update? It stays P0->S0?
    
    # Let's check App.py logic again.
    #     if not started_cube_sets: ...
    #     for player_id in new_mapping:
    #          self.hardware.add_player_started(player_id)
    
    # If new_mapping is {1: 1}, then Player 1 is marked started. Player 0 is NOT.
    # So the game is effectively running for Player 1?
    
    assert game._app.get_player_cube_set_mapping(1) == 1
    
    # Verify Hardware State
    assert game._app.hardware.has_player_started_game(1) is True
    assert game._app.hardware.has_player_started_game(0) is False

@async_test
async def test_mapping_two_players_simultaneous():
    """Verify mapping when both cube sets complete ABC."""
    game, mqtt, queue = await create_test_game(player_count=2)
    
    # Simulate Both Sets completing ABC
    cubes_to_game.reset_started_cube_sets()
    cubes_to_game.add_started_cube_set(1)
    cubes_to_game.add_started_cube_set(0)
    
    current_time = 1000
    await game._app.start(current_time)
    
    # Verify Mapping
    # calculate_player_mapping([0, 1]) -> sorted -> {0: 0, 1: 1}
    
    assert game._app.get_player_cube_set_mapping(0) == 0
    assert game._app.get_player_cube_set_mapping(1) == 1
    
    # Verify Hardware State
    assert game._app.hardware.has_player_started_game(0) is True
    assert game._app.hardware.has_player_started_game(1) is True

@async_test
async def test_late_join_rejected():
    """Verify late join is rejected once game is running."""
    game, mqtt, queue = await create_test_game(player_count=1)

    # 1. Start P0 on Set 0
    cubes_to_game.reset_started_cube_sets()
    cubes_to_game.add_started_cube_set(0)
    current_time = 1000
    await game._app.start(current_time)

    assert game._app.hardware.has_player_started_game(0) is True
    assert game._app.hardware.has_player_started_game(1) is False
    assert game.running is True

    # 2. Attempt late join (should be rejected)
    from input.input_devices import CubesInput
    input_dev = CubesInput(None)
    # 2. Attempt late join (should be rejected)
    from input.input_devices import CubesInput
    input_dev = CubesInput(None)
    # Grace period is 6s, so we need to be > 6s late
    result = await game.start(input_dev, current_time + 7000)

    # Verify join was rejected
    assert result == -1, "Late join should be rejected"
    assert game._app.player_count == 1, "Player count should remain 1"
    assert not game._app.hardware.has_player_started_game(1), "P1 should not be started"

    # Original player should continue playing normally
    assert game.running is True
    assert game._app.hardware.has_player_started_game(0) is True

