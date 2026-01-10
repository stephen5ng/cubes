import pytest
from typing import List
from tests.fixtures.game_factory import create_test_game, async_test, advance_frames
from tests.fixtures.mqtt_helpers import simulate_abc_sequence, process_mqtt_queue, inject_neighbor_report
from tests.assertions.game_assertions import assert_player_started
from hardware import cubes_to_game
from game.game_state import Game
from testing.fake_mqtt_client import FakeMqttClient
import asyncio

# Test Constants
ABC_COUNTDOWN_FRAMES = 50  # Frames needed for countdown completion and event propagation


def reset_abc_test_state(game: Game) -> int:
    """Reset game and cubes_to_game state for ABC countdown testing.

    Clears all running state to allow testing ABC sequences from scratch.

    Args:
        game: Game instance to reset

    Returns:
        Initial timestamp (always 0)
    """
    game.running = False
    cubes_to_game.set_game_running(False)
    # Clear started cube sets to allow re-testing ABC sequences
    cubes_to_game.reset_started_cube_sets()
    cubes_to_game.set_abc_countdown_delay(0)
    return 0  # now_ms


async def setup_abc_test(
    game: Game,
    mqtt: FakeMqttClient,
    queue: asyncio.Queue,
    player_cubes: List[List[str]],
    now_ms: int = 0
) -> None:
    """Initialize cubes for ABC countdown test.

    Isolates all cubes and activates ABC start mode.

    Args:
        game: Game instance
        mqtt: Fake MQTT client
        queue: Publish queue
        player_cubes: List of cube lists per player (e.g., [["1","2","3"], ["11","12","13"]])
        now_ms: Current timestamp
    """
    # Flatten all cubes and initialize as isolated
    all_cubes = [cube for player in player_cubes for cube in player]
    for cube in all_cubes:
        await inject_neighbor_report(mqtt, cube, "-")

    await process_mqtt_queue(game, queue, mqtt, now_ms)
    await cubes_to_game.activate_abc_start_if_ready(queue, now_ms)

@async_test
async def test_both_players_abc_simultaneous():
    """Test both players pressing ABC buttons simultaneously."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    now_ms = reset_abc_test_state(game)

    # Initialize cubes for both players (isolated)
    # P0: 1, 2, 3
    # P1: 11, 12, 13
    await setup_abc_test(game, mqtt, queue, [["1", "2", "3"], ["11", "12", "13"]], now_ms)

    # Connect cubes to form ABC sequence for both players
    # P0: 1->2->3
    await inject_neighbor_report(mqtt, "1", "2")
    await inject_neighbor_report(mqtt, "2", "3")

    # P1: 11->12->13
    await inject_neighbor_report(mqtt, "11", "12")
    await inject_neighbor_report(mqtt, "12", "13")

    await process_mqtt_queue(game, queue, mqtt, now_ms)
    # 4. Wait for game to start and racks to be populated
    # Use run_until_condition which advances frames until condition is met
    from tests.fixtures.game_factory import run_until_condition
    
    # Wait for player 0 to start
    await run_until_condition(game, queue, lambda fc, ms: game.running and len(game.racks[0].tiles) > 0, max_frames=200)

    # Verify both players started
    assert game.running, "Game should be running"

    assert_player_started(game, player=0)
    assert_player_started(game, player=1)

    # Verify both players have racks
    assert len(game.racks[0].tiles) > 0
    assert len(game.racks[1].tiles) > 0


@async_test
async def test_p0_only_abc():
    """Test only Player 0 pressing ABC buttons starts their game."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    now_ms = reset_abc_test_state(game)

    # Initialize P0 cubes only: 1, 2, 3
    await setup_abc_test(game, mqtt, queue, [["1", "2", "3"]], now_ms)

    # Connect P0 sequence: 1->2->3
    await inject_neighbor_report(mqtt, "1", "2")
    await inject_neighbor_report(mqtt, "2", "3")

    await process_mqtt_queue(game, queue, mqtt, now_ms)

    # Wait for game to start
    from tests.fixtures.game_factory import run_until_condition
    await run_until_condition(game, queue, lambda fc, ms: game.running, max_frames=200)

    # Verify P0 started, P1 did not
    assert game.running, "Game should be running"
    assert game._app.player_count == 1, "Player count should be 1"
    assert cubes_to_game.has_player_started_game(0), "Player 0 should have started"
    assert not cubes_to_game.has_player_started_game(1), "Player 1 should NOT have started"


@async_test
async def test_p1_only_abc():
    """Test only Player 1 pressing ABC buttons starts their game."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    now_ms = reset_abc_test_state(game)

    # Initialize P1 cubes only: 11, 12, 13
    await setup_abc_test(game, mqtt, queue, [["11", "12", "13"]], now_ms)

    # Connect P1 sequence: 11->12->13
    await inject_neighbor_report(mqtt, "11", "12")
    await inject_neighbor_report(mqtt, "12", "13")

    await process_mqtt_queue(game, queue, mqtt, now_ms)

    # Wait for game to start
    from tests.fixtures.game_factory import run_until_condition
    await run_until_condition(game, queue, lambda fc, ms: game.running, max_frames=200)

    # Verify P1 started, P0 did not
    assert game.running, "Game should be running"
    assert game._app.player_count == 1, "Player count should be 1"
    assert cubes_to_game.has_player_started_game(1), "Player 1 should have started"
    assert not cubes_to_game.has_player_started_game(0), "Player 0 should NOT have started"


@async_test
async def test_per_player_abc_tracking():
    """Test that ABC sequences are tracked independently per player (0 vs 1)."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    now_ms = reset_abc_test_state(game)

    # Initialize both players' cubes
    # P0: 1, 2, 3
    # P1: 11, 12, 13
    await setup_abc_test(game, mqtt, queue, [["1", "2", "3"], ["11", "12", "13"]], now_ms)

    # P0 forms "1-2" (incomplete sequence: A-B)
    await inject_neighbor_report(mqtt, "1", "2")
    # P0 Cube 2 is NOT connected to 3 yet
    await inject_neighbor_report(mqtt, "2", "-")

    # P1 forms "11-12-13" (complete sequence: A-B-C)
    await inject_neighbor_report(mqtt, "11", "12")
    await inject_neighbor_report(mqtt, "12", "13")

    await process_mqtt_queue(game, queue, mqtt, now_ms)

    # Advance frames for countdown
    await advance_frames(game, queue, frames=ABC_COUNTDOWN_FRAMES)

    # Verify P1 started
    assert game.running, "Game should be running"
    assert game._app.player_count == 1, "Player count should be 1"
    assert cubes_to_game.has_player_started_game(1), "Player 1 should have started"

    # Verify P0 did NOT start (incomplete sequence)
    assert not cubes_to_game.has_player_started_game(0), "Player 0 should NOT have started with incomplete sequence"


