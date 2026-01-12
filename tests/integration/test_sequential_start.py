import pytest
from typing import List
from tests.fixtures.game_factory import create_test_game, async_test, advance_frames, advance_seconds
from tests.fixtures.mqtt_helpers import (
    simulate_abc_sequence,
    process_mqtt_queue,
    inject_neighbor_report,
    reset_abc_test_state,
    setup_abc_test,
    simulate_word_formation,
    disconnect_player_cubes
)
from tests.assertions.game_assertions import assert_player_started
from tests.constants import ABC_COUNTDOWN_FRAMES
from hardware import cubes_to_game
from game.game_state import Game
from testing.fake_mqtt_client import FakeMqttClient
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.sequential
@pytest.mark.multiplayer
@pytest.mark.fast
@async_test
async def test_p1_cannot_join_after_p0_started():
    """Test that P1 cannot join after P0's game has started.

    Validates:
    - P0 can start and play alone via ABC sequence
    - Game continues running after P0 starts
    - P1 attempting ABC after game started is ignored (no ABC letters assigned)
    - P1 does not join the running game
    - P0's game continues uninterrupted

    Regression guard for: No late-join allowed once game is running
    """
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    now_ms = reset_abc_test_state(game)

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
    assert game._app.player_count == 1, "Should be single player"

    # Disconnect P0 cubes to prevent accidental words
    await disconnect_player_cubes(mqtt, ["1", "2", "3"])
    await process_mqtt_queue(game, queue, mqtt, now_ms)

    # --- P0 plays for a bit ---
    initial_score = game.scores[0].score
    await advance_seconds(game, queue, 5)

    # Verify P0 is still running ok
    assert game.racks[0].running
    assert game.running

    # --- P1 attempts to join (should fail) ---
    # P1 forms A-B-C: 11->12->13
    # This should be ignored since game is running
    await inject_neighbor_report(mqtt, "11", "12")
    await inject_neighbor_report(mqtt, "12", "13")

    await process_mqtt_queue(game, queue, mqtt, now_ms)

    # Advance frames (P1 won't get countdown since ABC is inactive)
    await advance_frames(game, queue, frames=ABC_COUNTDOWN_FRAMES)

    # Verify P1 did NOT join
    assert not cubes_to_game.has_player_started_game(1), "P1 should not be started"
    assert game._app.player_count == 1, "Should still be single player"
    assert game.running, "P0's game should continue running"
    assert game.racks[0].running, "P0's rack should still be running"

    # P0's state should be unaffected
    assert game.scores[0].score >= initial_score
    assert len(game.racks[0].tiles) > 0, "P0 rack should still have tiles"


@pytest.mark.sequential
@pytest.mark.multiplayer
@pytest.mark.fast
@async_test
async def test_p0_cannot_join_after_p1_started():
    """Test that P0 cannot join after P1's game has started."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    now_ms = reset_abc_test_state(game)

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
    assert not cubes_to_game.has_player_started_game(0)
    assert game._app.player_count == 1

    # Disconnect P1 cubes to prevent accidental words
    await disconnect_player_cubes(mqtt, ["11", "12", "13"])
    await process_mqtt_queue(game, queue, mqtt, now_ms)

    # --- P0 attempts to join (should fail) ---
    # P0 forms A-B-C: 1->2->3
    await inject_neighbor_report(mqtt, "1", "2")
    await inject_neighbor_report(mqtt, "2", "3")

    await process_mqtt_queue(game, queue, mqtt, now_ms)
    await advance_frames(game, queue, frames=ABC_COUNTDOWN_FRAMES)

    # Verify P0 did NOT join
    assert not cubes_to_game.has_player_started_game(0), "P0 should not be started"
    assert game._app.player_count == 1, "Should still be single player"
    assert game.running, "P1's game should continue running"
    assert game.racks[1].running, "P1's rack should still be running"
    assert len(game.racks[1].tiles) > 0, "P1 rack should still have tiles"
