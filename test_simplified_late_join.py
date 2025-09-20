#!/usr/bin/env python3

"""
Test for simplified late join behavior after ABC completion.

This test verifies:
1. First player can complete ABC sequence and start countdown
2. Once first player completes countdown, ABC state is cleared for all players 
3. Second player attempting ABC connection after ABC is cleared has no effect
"""

import asyncio
import logging
from unittest.mock import Mock
import cubes_to_game
import tiles
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

async def test_simplified_late_join():
    """Test simplified late join behavior."""
    
    # Clear any existing state
    cubes_to_game.abc_manager.reset()
    cubes_to_game._game_started_players.clear()
    
    # Setup test environment
    publish_queue = TestPublishQueue()
    mock_sound_manager = MockSoundManager()
    
    # Mock callbacks
    def mock_start_game_callback(auto_start, now_ms, player):
        print(f"GAME START CALLBACK: auto_start={auto_start} at {now_ms}ms for player {player}")
        return asyncio.create_task(asyncio.sleep(0))
    
    async def mock_guess_tiles_callback(guess, is_valid, player, now_ms):
        print(f"GUESS CALLBACK: {guess} (valid={is_valid}) for player {player} at {now_ms}ms")
    
    cubes_to_game.start_game_callback = mock_start_game_callback
    cubes_to_game.guess_tiles_callback = mock_guess_tiles_callback
    
    # Initialize cube managers for both players
    cubes_to_game.cube_managers[0].cube_list = ['1', '2', '3', '4', '5', '6']
    cubes_to_game.cube_managers[1].cube_list = ['11', '12', '13', '14', '15', '16']
    
    # Build the cube-to-player mapping
    cubes_to_game.cube_to_player = {}
    for i, cube in enumerate(cubes_to_game.cube_managers[0].cube_list):
        cubes_to_game.cube_to_player[cube] = 0
    for i, cube in enumerate(cubes_to_game.cube_managers[1].cube_list):
        cubes_to_game.cube_to_player[cube] = 1
    
    print("============================================================")
    print("TESTING SIMPLIFIED LATE JOIN BEHAVIOR")
    print("============================================================")
    
    print("\n1. SETUP NEIGHBOR REPORTS FOR BOTH PLAYERS")
    current_time = 1000
    
    # Player 0: Set up neighbor reports
    for cube in ['1', '2', '3', '4', '5', '6']:
        neighbor = "-"  # All cubes report no neighbors for simplicity
        await cubes_to_game.handle_mqtt_message(publish_queue,
            Mock(topic=Mock(value=f"cube/right/{cube}"), payload=Mock(decode=lambda n=neighbor: n)),
            current_time, mock_sound_manager)
    
    # Player 1: Set up neighbor reports
    for cube in ['11', '12', '13', '14', '15', '16']:
        neighbor = "-"  # All cubes report no neighbors for simplicity
        await cubes_to_game.handle_mqtt_message(publish_queue,
            Mock(topic=Mock(value=f"cube/right/{cube}"), payload=Mock(decode=lambda n=neighbor: n)),
            current_time, mock_sound_manager)
    
    print("✓ Neighbor reports set up for both players")
    
    print("\n2. ACTIVATE ABC SEQUENCE")
    current_time = 2000
    await cubes_to_game.activate_abc_start_if_ready(publish_queue, current_time)
    
    assert cubes_to_game.abc_manager.abc_start_active, "ABC sequence should be active"
    assert 0 in cubes_to_game.abc_manager.player_abc_cubes, "Player 0 should have ABC assignments"
    assert 1 in cubes_to_game.abc_manager.player_abc_cubes, "Player 1 should have ABC assignments"
    print("✓ ABC sequence activated for both players")
    
    # Get ABC cube assignments
    p0_abc = cubes_to_game.abc_manager.player_abc_cubes[0]
    p1_abc = cubes_to_game.abc_manager.player_abc_cubes[1]
    print(f"Player 0 ABC: A={p0_abc['A']}, B={p0_abc['B']}, C={p0_abc['C']}")
    print(f"Player 1 ABC: A={p1_abc['A']}, B={p1_abc['B']}, C={p1_abc['C']}")
    
    print("\n3. PLAYER 0 COMPLETES ABC SEQUENCE AND FULL COUNTDOWN")
    current_time = 3000
    publish_queue.messages.clear()
    
    # Connect Player 0's ABC cubes in sequence: A->B->C
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p0_abc['A']}"), payload=Mock(decode=lambda: p0_abc['B'])),
        current_time, mock_sound_manager)
    
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p0_abc['B']}"), payload=Mock(decode=lambda: p0_abc['C'])),
        current_time, mock_sound_manager)
    
    # Verify Player 0 is in countdown
    assert 0 in cubes_to_game.abc_manager.player_countdown_active, "Player 0 should be in countdown"
    print("✓ Player 0 started countdown")
    
    # Let Player 0's countdown complete fully
    for time_step in range(3100, 10000, 100):
        incidents = await cubes_to_game.abc_manager.check_countdown_completion(publish_queue, time_step, mock_sound_manager)
        if 0 in cubes_to_game._game_started_players:
            print(f"✓ Player 0 completed countdown at time {time_step}ms")
            break
    
    assert 0 in cubes_to_game._game_started_players, "Player 0 should have started game"
    print("✓ Player 0 game started")
    
    print("\n4. VERIFY ABC STATE IS COMPLETELY CLEARED")
    assert not cubes_to_game.abc_manager.abc_start_active, "ABC should no longer be active"
    assert not cubes_to_game.abc_manager.player_abc_cubes, "No ABC assignments should exist"
    assert not cubes_to_game.abc_manager.player_countdown_active, "No countdown should be active"
    print("✓ ABC state completely cleared after Player 0 completion")
    
    print("\n5. PLAYER 1 ATTEMPTS ABC CONNECTIONS (SHOULD HAVE NO EFFECT)")
    current_time = time_step + 1000
    publish_queue.messages.clear()
    
    # Player 1 tries to connect cubes, but ABC state is cleared so this should do nothing special
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p1_abc['A']}"), payload=Mock(decode=lambda: p1_abc['B'])),
        current_time, mock_sound_manager)
    
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p1_abc['B']}"), payload=Mock(decode=lambda: p1_abc['C'])),
        current_time, mock_sound_manager)
    
    # Verify Player 1 cannot start countdown (ABC is cleared)
    assert 1 not in cubes_to_game.abc_manager.player_countdown_active, "Player 1 should not be in countdown"
    assert 1 not in cubes_to_game._game_started_players, "Player 1 game should not be started"
    assert not cubes_to_game.abc_manager.abc_start_active, "ABC should still be inactive"
    print("✓ Player 1 ABC connections have no special effect - ABC is cleared")
    
    print("\n6. VERIFY ONLY PLAYER 0 STARTED GAME")
    assert 0 in cubes_to_game._game_started_players, "Player 0 game should be started"
    assert 1 not in cubes_to_game._game_started_players, "Player 1 game should not be started"
    print("✓ Only Player 0 started game successfully")
    
    print("\n🎉 TEST PASSED!")
    print("Simplified late join behavior working correctly!")
    print("- First player can complete ABC and start countdown")
    print("- ABC state is cleared when first player completes countdown")
    print("- Second player connections have no special effect after ABC is cleared")
    return True

async def main():
    try:
        success = await test_simplified_late_join()
        if success:
            print("\n============================================================")
            print("SIMPLIFIED LATE JOIN BEHAVIOR WORKING CORRECTLY!")
            print("============================================================")
        else:
            print("\n❌ Test failed")
            return False
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)