import pytest
from tests.fixtures.game_factory import create_test_game, async_test, advance_frames
from tests.fixtures.mqtt_helpers import simulate_abc_sequence, process_mqtt_queue, inject_neighbor_report
from tests.assertions.game_assertions import assert_player_started
from hardware import cubes_to_game

@async_test
async def test_both_players_abc_simultaneous():
    """Test both players pressing ABC buttons simultaneously."""
    game, mqtt, queue = await create_test_game(descent_mode="discrete")
    
    # Reset game state to start from scratch
    game.running = False
    cubes_to_game.set_abc_countdown_delay(0)
    now_ms = 0

    # 1. Initialize cubes for both players (isolated)
    # P0: 1, 2, 3
    # P1: 11, 12, 13
    for cube in ["1", "2", "3", "11", "12", "13"]:
        await inject_neighbor_report(mqtt, cube, "-")
    
    await process_mqtt_queue(game, queue, mqtt, now_ms)

    # 2. Activate ABC assignment
    # This mimics main.py calling it at startup
    await cubes_to_game.activate_abc_start_if_ready(queue, now_ms)

    # 3. Connect cubes to form ABC sequence for both players
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
