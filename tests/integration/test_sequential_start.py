import pytest
from typing import List
from tests.fixtures.game_factory import create_test_game, async_test, advance_frames
from tests.fixtures.mqtt_helpers import (
    simulate_abc_sequence, 
    process_mqtt_queue, 
    inject_neighbor_report,
    reset_abc_test_state,
    setup_abc_test,
    setup_abc_test,
    simulate_word_formation,
    disconnect_player_cubes
)
from tests.assertions.game_assertions import assert_player_started
from hardware import cubes_to_game
from game.game_state import Game
from testing.fake_mqtt_client import FakeMqttClient
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# Reuse constant
ABC_COUNTDOWN_FRAMES = 50

@async_test
async def test_p1_joins_after_p0_started():
    """Test P1 joining after P0 has already started playing."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    now_ms = reset_abc_test_state(game)

    # Patch guess_tiles to prevent accidental words from forking racks
    # asking for forgiveness: modifying instance method
    original_guess_tiles = game._app.guess_tiles
    game._app.guess_tiles = AsyncMock()

    # Initialize cubes for both players
    # P0: 1, 2, 3
    # P1: 11, 12, 13
    await setup_abc_test(game, mqtt, queue, [["1", "2", "3"], ["11", "12", "13"]], now_ms)

    # --- Start P0 ---
    # P0 forms A-B-C: 1->2->3
    await inject_neighbor_report(mqtt, "1", "2")
    await inject_neighbor_report(mqtt, "2", "3")
    
    await process_mqtt_queue(game, queue, mqtt, now_ms)
    
    # Wait for start
    await advance_frames(game, queue, frames=ABC_COUNTDOWN_FRAMES)
    
    # Verify P0 started
    assert game.running, "Game should be running"
    assert_player_started(game, player=0)
    assert not cubes_to_game.has_player_started_game(1), "P1 should not be started yet"
    
    # Disconnect P0 cubes to prevent accidental words (e.g. "GAL")
    await disconnect_player_cubes(mqtt, ["1", "2", "3"])
    await process_mqtt_queue(game, queue, mqtt, now_ms)

    # --- P0 plays for a bit ---
    # Advance time to simulate gameplay (e.g., 5 seconds)
    # This ensures P0 state progresses
    initial_score = game.scores[0].score
    await advance_frames(game, queue, frames=300) # ~5 seconds at 60fps
    
    # Verify P0 is still running ok
    assert game.racks[0].running
    
    # --- Start P1 ---
    # P1 forms A-B-C: 11->12->13
    await inject_neighbor_report(mqtt, "11", "12")
    await inject_neighbor_report(mqtt, "12", "13")
    
    await process_mqtt_queue(game, queue, mqtt, now_ms)
    
    # Wait for P1 start (countdown?)
    # Note: If game is already running, does P1 need countdown?
    # Based on logic, ABC sequence triggers check_countdown_completion.
    # We suspect it might be faster or immediate if game is running, but let's assume consistent behavior.
    await advance_frames(game, queue, frames=ABC_COUNTDOWN_FRAMES)
    
    # Verify P1 started
    assert_player_started(game, player=1)
    
    # Verify P1 has correct rack state (fresh)
    assert len(game.racks[1].tiles) > 0, "P1 rack not populated"
    assert game.scores[1].score == 0, "P1 score should start at 0"
    
    # Verify P0 state preserved
    # Score might not change if no words formed, but should be at least initial
    assert game.scores[0].score >= initial_score
    assert game.racks[0].running, "P0 should still be running"

    # Verify independent racks
    p0_tiles = game._app._player_racks[0].get_tiles()
    p1_tiles = game._app._player_racks[1].get_tiles()
    
    # Since P0 has NOT played a word yet (only advanced time), racks should be IDENTICAL
    # (User requirement: players start with same letters)
    assert p0_tiles == p1_tiles, "Racks should be identical (shared start)"

    # --- Verify Independence (Copy-on-Write) ---
    # Manually modify P0's rack to simulate a move without relying on random dictionary words
    # This proves that if P0 changes their rack, P1 is unaffected (independent history)
    current_p0_tiles = game._app._player_racks[0].get_tiles()
    # Force a new list for P0 (simulating copy-on-write logic in App.guess_tiles)
    new_p0_tiles = list(current_p0_tiles)
    if new_p0_tiles:
        new_p0_tiles.pop() # Remove one tile
        game._app._player_racks[0].set_tiles(new_p0_tiles)
    
    # Verify divergence
    p0_tiles_after = game._app._player_racks[0].get_tiles()
    p1_tiles_after = game._app._player_racks[1].get_tiles()
    
    assert p0_tiles_after != p1_tiles_after, "Racks should diverge after P0 modifies their rack"
    assert len(p0_tiles_after) != len(p1_tiles_after), "Lengths should differ"
    assert p1_tiles_after == p1_tiles, "P1 rack should remain unchanged (independent)"


@async_test
async def test_p1_starts_first():
    """Test P1 starting first, then P0 joins."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    now_ms = reset_abc_test_state(game)

    # Patch guess_tiles to prevent accidental words
    game._app.guess_tiles = AsyncMock()

    # Initialize cubes
    await setup_abc_test(game, mqtt, queue, [["1", "2", "3"], ["11", "12", "13"]], now_ms)

    # --- Start P1 ---
    # P1 forms A-B-C: 11->12->13
    await inject_neighbor_report(mqtt, "11", "12")
    await inject_neighbor_report(mqtt, "12", "13")
    
    await process_mqtt_queue(game, queue, mqtt, now_ms)
    await advance_frames(game, queue, frames=ABC_COUNTDOWN_FRAMES)
    
    # Verify P1 started
    assert game.running
    assert_player_started(game, player=1)
    
    # Disconnect P1 cubes to prevent accidental words
    await disconnect_player_cubes(mqtt, ["11", "12", "13"])
    await process_mqtt_queue(game, queue, mqtt, now_ms)
    
    # Verify P0 NOT started
    assert not cubes_to_game.has_player_started_game(0)
    
    # --- Start P0 ---
    # P0 forms A-B-C: 1->2->3
    await inject_neighbor_report(mqtt, "1", "2")
    await inject_neighbor_report(mqtt, "2", "3")
    
    await process_mqtt_queue(game, queue, mqtt, now_ms)
    await advance_frames(game, queue, frames=ABC_COUNTDOWN_FRAMES)
    
    # Verify P0 started
    assert_player_started(game, player=0)
    
    # Disconnect P0 cubes
    await disconnect_player_cubes(mqtt, ["1", "2", "3"])
    await process_mqtt_queue(game, queue, mqtt, now_ms)
    
    assert len(game.racks[0].tiles) > 0 # Display racks (checking visibility)
    
    # Independence check
    # P1 hasn't played, P0 joined. Racks should match start state (Shared Start).
    assert game._app._player_racks[0].get_tiles() == game._app._player_racks[1].get_tiles()
