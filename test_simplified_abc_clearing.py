#!/usr/bin/env python3

"""
Test for the simplified ABC clearing logic.

This test verifies:
1. When any player completes their countdown, ABC letters are cleared from ALL cubes
2. Players who complete ABC after this happens cannot start a countdown (no ABC state exists)
3. The visual experience is clean - no ABC letters remain after someone completes countdown
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

async def test_simplified_abc_clearing():
    """Test that ABC letters are cleared from all cubes when any player completes countdown."""
    
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
    print("TESTING SIMPLIFIED ABC CLEARING LOGIC")
    print("============================================================")
    
    print("\n1. SETUP NEIGHBOR REPORTS FOR BOTH PLAYERS")
    current_time = 1000
    
    # Player 0: Set up neighbor reports
    for cube in ['1', '2', '3', '4', '5', '6']:
        neighbor = "-"
        await cubes_to_game.handle_mqtt_message(publish_queue,
            Mock(topic=Mock(value=f"cube/right/{cube}"), payload=Mock(decode=lambda n=neighbor: n)),
            current_time, mock_sound_manager)
    
    # Player 1: Set up neighbor reports
    for cube in ['11', '12', '13', '14', '15', '16']:
        neighbor = "-"
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
    
    print("\n3. PLAYER 0 COMPLETES ABC SEQUENCE AND FINISHES COUNTDOWN")
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
    
    print("\n4. ADVANCE TIME UNTIL PLAYER 0 COMPLETES COUNTDOWN")
    # Simulate time progression to complete countdown
    for time_step in range(4000, 10000, 100):  # Advance time until countdown completes
        incidents = await cubes_to_game.abc_manager.check_countdown_completion(publish_queue, time_step)
        
        # Check if Player 0 has completed countdown
        if 0 in cubes_to_game._game_started_players:
            print(f"✓ Player 0 completed countdown at time {time_step}ms")
            break
    
    # Verify Player 0 started and ABC state was cleared
    assert 0 in cubes_to_game._game_started_players, "Player 0 game should be started"
    assert not cubes_to_game.abc_manager.abc_start_active, "ABC should no longer be active"
    assert not cubes_to_game.abc_manager.player_abc_cubes, "No players should have ABC assignments"
    print("✓ ABC state cleared for all players after Player 0 completed countdown")
    
    # Count blank messages for ABC cubes (should have been cleared)
    blank_messages = [msg for msg in publish_queue.messages if msg[1] == " "]
    abc_cubes_cleared = set()
    for msg in blank_messages:
        topic = msg[0]  # e.g., "cube/1/letter"
        if "/letter" in topic:
            cube_id = topic.split('/')[1]
            if cube_id in [p0_abc['A'], p0_abc['B'], p0_abc['C'], p1_abc['A'], p1_abc['B'], p1_abc['C']]:
                abc_cubes_cleared.add(cube_id)
    
    print(f"ABC cubes cleared to blank: {sorted(abc_cubes_cleared)}")
    assert len(abc_cubes_cleared) == 6, f"All 6 ABC cubes should be cleared, got {len(abc_cubes_cleared)}"
    print("✓ All ABC letters cleared from cubes")
    
    print("\n5. PLAYER 1 TRIES TO COMPLETE ABC AFTER CLEARING (SHOULD DO NOTHING)")
    current_time = time_step + 1000
    publish_queue.messages.clear()
    
    # Player 1 tries to complete ABC sequence after ABC state is cleared
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p1_abc['A']}"), payload=Mock(decode=lambda: p1_abc['B'])),
        current_time, mock_sound_manager)
    
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p1_abc['B']}"), payload=Mock(decode=lambda: p1_abc['C'])),
        current_time, mock_sound_manager)
    
    # Verify Player 1 cannot start countdown (no ABC state exists)
    assert 1 not in cubes_to_game.abc_manager.player_countdown_active, "Player 1 should not be able to start countdown"
    assert 1 not in cubes_to_game._game_started_players, "Player 1 should not have started game"
    assert not cubes_to_game.abc_manager.abc_start_active, "ABC should still be inactive"
    print("✓ Player 1 cannot complete ABC after state was cleared")
    
    # Verify no new messages were sent (no countdown started)
    countdown_messages = [msg for msg in publish_queue.messages if msg[1] == "?"]
    assert len(countdown_messages) == 0, "No countdown messages should be sent"
    print("✓ No countdown messages sent for Player 1")
    
    print("\n🎉 TEST PASSED!")
    print("Simplified ABC clearing logic working correctly!")
    print("- ABC letters cleared from all cubes when countdown completes")
    print("- Players cannot complete ABC after state is cleared")
    print("- Clean visual experience - no leftover ABC letters")
    return True

async def main():
    try:
        success = await test_simplified_abc_clearing()
        if success:
            print("\n============================================================")
            print("SIMPLIFIED ABC CLEARING LOGIC WORKING CORRECTLY!")
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