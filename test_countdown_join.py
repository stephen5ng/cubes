#!/usr/bin/env python3

"""
Test for the feature where second player can join during first player's ABC countdown.
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

async def test_countdown_join():
    """Test that second player can join during first player's countdown."""
    
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
    print("TESTING SECOND PLAYER JOINING DURING COUNTDOWN")
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
    
    print("\n3. PLAYER 0 COMPLETES ABC SEQUENCE (STARTS COUNTDOWN)")
    current_time = 3000
    publish_queue.messages.clear()
    
    # Connect Player 0's ABC cubes in sequence: A->B->C
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p0_abc['A']}"), payload=Mock(decode=lambda: p0_abc['B'])),
        current_time, mock_sound_manager)
    
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p0_abc['B']}"), payload=Mock(decode=lambda: p0_abc['C'])),
        current_time, mock_sound_manager)
    
    # Verify Player 0 is in countdown but not game started yet
    assert 0 in cubes_to_game.abc_manager.player_countdown_active, "Player 0 should be in countdown"
    assert 0 not in cubes_to_game._game_started_players, "Player 0 game should not be started yet"
    assert 1 not in cubes_to_game.abc_manager.player_countdown_active, "Player 1 should not be in countdown yet"
    assert 1 not in cubes_to_game._game_started_players, "Player 1 game should not be started yet"
    print("✓ Player 0 started countdown, Player 1 not yet started")
    
    print("\n4. PLAYER 1 COMPLETES ABC SEQUENCE DURING PLAYER 0'S COUNTDOWN")
    current_time = 3500  # 500ms after Player 0 started countdown
    
    # Connect Player 1's ABC cubes in sequence: A->B->C
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p1_abc['A']}"), payload=Mock(decode=lambda: p1_abc['B'])),
        current_time, mock_sound_manager)
    
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p1_abc['B']}"), payload=Mock(decode=lambda: p1_abc['C'])),
        current_time, mock_sound_manager)
    
    # Verify both players are now in countdown
    assert 0 in cubes_to_game.abc_manager.player_countdown_active, "Player 0 should still be in countdown"
    assert 1 in cubes_to_game.abc_manager.player_countdown_active, "Player 1 should now be in countdown"
    assert 0 not in cubes_to_game._game_started_players, "Player 0 game should not be started yet"
    assert 1 not in cubes_to_game._game_started_players, "Player 1 game should not be started yet"
    print("✓ Player 1 joined countdown during Player 0's countdown")
    
    print("\n5. SIMULATE COUNTDOWN COMPLETION")
    # Simulate time progression to complete countdown for both players
    for time_step in range(4000, 10000, 100):  # Advance time until both countdowns complete
        incidents = await cubes_to_game.abc_manager.check_countdown_completion(publish_queue, time_step)
        
        # Check if both players have started
        if 0 in cubes_to_game._game_started_players and 1 in cubes_to_game._game_started_players:
            print(f"✓ Both players completed countdown at time {time_step}ms")
            break
    
    # Verify final state
    assert 0 in cubes_to_game._game_started_players, "Player 0 game should be started"
    assert 1 in cubes_to_game._game_started_players, "Player 1 game should be started"
    print("✓ Both players successfully started their games")
    
    # Count the "?" replacements for each player
    question_mark_messages = [msg for msg in publish_queue.messages if msg[1] == "?"]
    
    # Get unique cube replacements for each player (avoid counting duplicates)
    p0_cubes_replaced = set()
    p1_cubes_replaced = set()
    
    for msg in question_mark_messages:
        topic = msg[0]  # e.g., "cube/1/letter"
        if "/letter" in topic:
            cube_id = topic.split('/')[1]
            if cube_id in cubes_to_game.cube_managers[0].cube_list:
                p0_cubes_replaced.add(cube_id)
            elif cube_id in cubes_to_game.cube_managers[1].cube_list:
                p1_cubes_replaced.add(cube_id)
    
    print(f"Player 0 had {len(p0_cubes_replaced)} unique cubes replaced with '?': {sorted(p0_cubes_replaced)}")
    print(f"Player 1 had {len(p1_cubes_replaced)} unique cubes replaced with '?': {sorted(p1_cubes_replaced)}")
    
    # Both players should have had their cubes replaced
    assert len(p0_cubes_replaced) == 6, f"Player 0 should have 6 cube replacements, got {len(p0_cubes_replaced)}"
    assert len(p1_cubes_replaced) == 6, f"Player 1 should have 6 cube replacements, got {len(p1_cubes_replaced)}"
    print("✓ Both players had their cubes synchronized to '?' during countdown")
    
    print("\n🎉 TEST PASSED!")
    print("Second player successfully joined during first player's countdown!")
    print("Both players' cubes were synchronized correctly!")
    return True

async def main():
    try:
        success = await test_countdown_join()
        if success:
            print("\n============================================================")
            print("COUNTDOWN JOIN FEATURE WORKING CORRECTLY!")
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