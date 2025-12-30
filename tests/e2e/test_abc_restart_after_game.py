#!/usr/bin/env python3

"""
Test for ABC restart after game end.

This test verifies:
1. After a game completes, players can line up ABC to start a new game
2. The abc_manager state is properly reset after game completion  
3. New ABC assignments work correctly after game end
"""

import asyncio
import logging
from unittest.mock import Mock
from blockwords.hardware import cubes_to_game
from blockwords.core import tiles
from src.testing.mock_sound_manager import MockSoundManager

# Set up basic logging to see what's happening
logging.basicConfig(level=logging.INFO)

class TestPublishQueue:
    def __init__(self):
        self.messages = []
    
    async def put(self, message):
        topic, payload, retain, timestamp = message
        self.messages.append(message)
        print(f"MQTT: {topic} -> {payload} (retain={retain}) at {timestamp}ms")

async def test_abc_restart_after_game():
    """Test that ABC can restart a new game after the previous game completes."""
    
    # Clear any existing state
    cubes_to_game.abc_manager.reset()
    cubes_to_game._game_started_players.clear()
    
    # Setup test environment
    publish_queue = TestPublishQueue()
    mock_sound_manager = MockSoundManager()
    
    # Track game starts
    game_starts = []
    
    # Mock callbacks
    async def mock_start_game_callback(auto_start, now_ms, player):
        print(f"GAME START CALLBACK: auto_start={auto_start} at {now_ms}ms for player {player}")
        game_starts.append((player, now_ms))
        return
    
    async def mock_guess_tiles_callback(guess, is_valid, player, now_ms):
        print(f"GUESS CALLBACK: {guess} (valid={is_valid}) for player {player} at {now_ms}ms")
    
    cubes_to_game.start_game_callback = mock_start_game_callback
    cubes_to_game.guess_tiles_callback = mock_guess_tiles_callback
    
    # Initialize with test cubes (P0: cubes 1-6, P1: cubes 11-16)
    mock_client = Mock()
    mock_client.subscribe = Mock(return_value=asyncio.create_task(asyncio.sleep(0)))
    await cubes_to_game.init(mock_client)
    
    print("\n=== PHASE 1: Setup initial neighbor reports ===")
    now_ms = 1000
    
    # Give all cubes initial neighbor reports (all isolated)
    for cube_id in ["1", "2", "3", "4", "5", "6"]:
        await cubes_to_game.handle_mqtt_message(publish_queue,
                                               Mock(topic=Mock(value=f"cube/right/{cube_id}"), payload=b"-"),
                                               now_ms, mock_sound_manager)
    
    for cube_id in ["11", "12", "13", "14", "15", "16"]:
        await cubes_to_game.handle_mqtt_message(publish_queue,
                                               Mock(topic=Mock(value=f"cube/right/{cube_id}"), payload=b"-"),
                                               now_ms, mock_sound_manager)
    
    print("\n=== PHASE 2: Activate ABC and complete first game ===")
    now_ms = 2000
    
    # Activate ABC sequence
    await cubes_to_game.activate_abc_start_if_ready(publish_queue, now_ms)
    assert cubes_to_game.abc_manager.abc_start_active, "ABC start should be active"
    
    # Create A-B-C chain for Player 0 using their assigned ABC cubes
    p0_abc = cubes_to_game.abc_manager.player_abc_cubes[0]
    cube_a, cube_b, cube_c = p0_abc["A"], p0_abc["B"], p0_abc["C"]
    print(f"Player 0 ABC assignment: A={cube_a}, B={cube_b}, C={cube_c}")
    
    # Form A->B->C chain
    await cubes_to_game.handle_mqtt_message(publish_queue,
                                           Mock(topic=Mock(value=f"cube/right/{cube_a}"), payload=cube_b.encode()),
                                           now_ms, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
                                           Mock(topic=Mock(value=f"cube/right/{cube_b}"), payload=cube_c.encode()),
                                           now_ms, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
                                           Mock(topic=Mock(value=f"cube/right/{cube_c}"), payload=b"-"),
                                           now_ms, mock_sound_manager)
    
    # Check ABC completion triggers countdown
    completed_player = await cubes_to_game.abc_manager.check_abc_sequence_complete()
    assert completed_player == 0, f"Player 0 should complete ABC, got {completed_player}"
    
    # Handle ABC completion
    await cubes_to_game.abc_manager.handle_abc_completion(publish_queue, completed_player, now_ms, None)
    assert 0 in cubes_to_game.abc_manager.player_countdown_active, "Player 0 should be in countdown"
    
    # Fast-forward through countdown to game start
    countdown_complete_time = cubes_to_game.abc_manager.countdown_complete_time
    now_ms = countdown_complete_time + 100
    
    # Process countdown completion
    incidents = await cubes_to_game.check_countdown_completion(publish_queue, now_ms, mock_sound_manager)
    
    # Verify game started and state was reset
    assert len(game_starts) == 1, f"Expected 1 game start, got {len(game_starts)}"
    assert game_starts[0][0] == 0, "Player 0 should have started game"
    assert not cubes_to_game.abc_manager.abc_start_active, "ABC start should be inactive after reset"
    assert not cubes_to_game.abc_manager.player_countdown_active, "No players should be in countdown after reset"
    assert not cubes_to_game.abc_manager.player_abc_cubes, "ABC assignments should be cleared after reset"
    
    print("\n=== PHASE 3: Test ABC restart after game completion ===")
    now_ms = 5000
    
    # Clear the game_starts list for the second game
    game_starts.clear()
    
    # Activate ABC sequence again (this should work after reset)
    await cubes_to_game.activate_abc_start_if_ready(publish_queue, now_ms)
    assert cubes_to_game.abc_manager.abc_start_active, "ABC start should be active again after game end"
    
    # Verify new ABC assignments were made
    assert 0 in cubes_to_game.abc_manager.player_abc_cubes, "Player 0 should have new ABC assignments"
    assert 1 in cubes_to_game.abc_manager.player_abc_cubes, "Player 1 should have ABC assignments too"
    
    # Get the new ABC assignments for Player 1
    p1_abc = cubes_to_game.abc_manager.player_abc_cubes[1]
    cube_a1, cube_b1, cube_c1 = p1_abc["A"], p1_abc["B"], p1_abc["C"]
    print(f"Player 1 ABC assignment: A={cube_a1}, B={cube_b1}, C={cube_c1}")
    
    # Form A->B->C chain for Player 1
    await cubes_to_game.handle_mqtt_message(publish_queue,
                                           Mock(topic=Mock(value=f"cube/right/{cube_a1}"), payload=cube_b1.encode()),
                                           now_ms, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
                                           Mock(topic=Mock(value=f"cube/right/{cube_b1}"), payload=cube_c1.encode()),
                                           now_ms, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
                                           Mock(topic=Mock(value=f"cube/right/{cube_c1}"), payload=b"-"),
                                           now_ms, mock_sound_manager)
    
    # Check ABC completion for Player 1
    completed_player = await cubes_to_game.abc_manager.check_abc_sequence_complete()
    assert completed_player == 1, f"Player 1 should complete ABC, got {completed_player}"
    
    # Handle ABC completion for Player 1
    await cubes_to_game.abc_manager.handle_abc_completion(publish_queue, completed_player, now_ms, None)
    assert 1 in cubes_to_game.abc_manager.player_countdown_active, "Player 1 should be in countdown"
    
    # Fast-forward through countdown to second game start
    countdown_complete_time = cubes_to_game.abc_manager.countdown_complete_time
    now_ms = countdown_complete_time + 100
    
    # Process countdown completion for second game
    incidents = await cubes_to_game.check_countdown_completion(publish_queue, now_ms, mock_sound_manager)
    
    # Verify second game started
    assert len(game_starts) == 1, f"Expected 1 game start in second round, got {len(game_starts)}"
    assert game_starts[0][0] == 1, "Player 1 should have started the second game"
    
    print("\n✓ Test passed: ABC can successfully restart after game completion")
    print("✓ ABC manager state is properly reset after each game")
    print("✓ New ABC assignments work correctly for subsequent games")

if __name__ == "__main__":
    asyncio.run(test_abc_restart_after_game())