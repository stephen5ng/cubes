#!/usr/bin/env python3
"""
Test per-player ABC sequence behavior with simplified clearing logic.

This test verifies:
1. ABC sequence displays on non-touching cubes for both players
2. Completing ABC for Player 0 starts game and clears ABC state for all players
3. Player 1 cannot complete ABC after Player 0 finishes (ABC state cleared)
4. Only players with active games receive letters
5. Per-player letter loading works correctly when games are active
"""

import asyncio
import logging
from unittest.mock import Mock, AsyncMock
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(__file__))

import cubes_to_game
import tiles
from src.testing.mock_sound_manager import MockSoundManager

# Test configuration
TEST_TIMEOUT = 10.0

class TestPublishQueue:
    def __init__(self):
        self.messages = []
    
    async def put(self, message):
        self.messages.append(message)
        topic, payload, retain, timestamp = message
        print(f"MQTT: {topic} -> {payload} (retain={retain}) at {timestamp}ms")

class TestResults:
    def __init__(self):
        self.abc_displayed_p0 = False
        self.abc_displayed_p1 = False
        self.game_started_p0 = False
        self.game_started_p1 = False
        self.letters_sent_p0 = False
        self.letters_sent_p1 = False

async def test_per_player_abc_sequence():
    """Test per-player ABC sequence behavior."""
    print("=" * 60)
    print("TESTING PER-PLAYER ABC SEQUENCE")
    print("=" * 60)
    
    # Initialize the system
    mock_client = Mock()
    mock_client.subscribe = AsyncMock()
    
    await cubes_to_game.init(mock_client)
    
    # Setup test queue and results
    publish_queue = TestPublishQueue()
    mock_sound_manager = MockSoundManager()
    results = TestResults()
    
    # Mock the callbacks
    def mock_start_game_callback(auto_start, now_ms, player):
        print(f"GAME START CALLBACK: auto_start={auto_start} at {now_ms}ms for player {player}")
        return asyncio.create_task(asyncio.sleep(0))
    
    async def mock_guess_tiles_callback(guess, is_valid, player, now_ms):
        print(f"GUESS CALLBACK: {guess} (valid={is_valid}) for player {player} at {now_ms}ms")
    
    cubes_to_game.start_game_callback = mock_start_game_callback
    cubes_to_game.guess_tiles_callback = mock_guess_tiles_callback
    
    print("\n1. INITIAL STATE - No ABC sequence active")
    assert not cubes_to_game.abc_manager.abc_start_active
    assert len(cubes_to_game._game_started_players) == 0
    print("✓ Initial state correct")
    
    print("\n2. SIMULATE NEIGHBOR REPORTS")
    # Simulate neighbor reports so ABC can activate (need at least 3 cubes from one player)
    current_time = 1000
    
    # Player 0: More neighbor reports to meet the 3-cube minimum
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/1"), payload=Mock(decode=lambda: "-")),
        current_time, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/2"), payload=Mock(decode=lambda: "3")),
        current_time, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/3"), payload=Mock(decode=lambda: "-")),
        current_time, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/4"), payload=Mock(decode=lambda: "-")),
        current_time, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/5"), payload=Mock(decode=lambda: "-")),
        current_time, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/6"), payload=Mock(decode=lambda: "-")),
        current_time, mock_sound_manager)
    
    # Player 1: Also add enough reports for player 1
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/11"), payload=Mock(decode=lambda: "-")),
        current_time, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/12"), payload=Mock(decode=lambda: "13")),
        current_time, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/13"), payload=Mock(decode=lambda: "-")),
        current_time, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/14"), payload=Mock(decode=lambda: "-")),
        current_time, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/15"), payload=Mock(decode=lambda: "-")),
        current_time, mock_sound_manager)
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value="cube/right/16"), payload=Mock(decode=lambda: "-")),
        current_time, mock_sound_manager)
    
    print("✓ Neighbor reports processed")
    
    print("\n3. ACTIVATE ABC SEQUENCE")
    current_time = 2000
    await cubes_to_game.activate_abc_start_if_ready(publish_queue, current_time)
    
    # Check that ABC is now active
    assert cubes_to_game.abc_manager.abc_start_active
    print("✓ ABC sequence activated")
    
    # Analyze the published messages to see where ABC letters were sent
    abc_messages = [msg for msg in publish_queue.messages if 'letter' in msg[0] and msg[1] in ['A', 'B', 'C']]
    
    p0_abc_cubes = []
    p1_abc_cubes = []
    
    for topic, letter, retain, timestamp in abc_messages:
        cube_id = topic.split('/')[1]
        if cube_id in ['1', '2', '3', '4', '5', '6']:
            p0_abc_cubes.append((cube_id, letter))
        elif cube_id in ['11', '12', '13', '14', '15', '16']:
            p1_abc_cubes.append((cube_id, letter))
    
    print(f"Player 0 ABC assignments: {p0_abc_cubes}")
    print(f"Player 1 ABC assignments: {p1_abc_cubes}")
    
    # Verify both players got ABC assignments
    assert len(p0_abc_cubes) == 3, f"Player 0 should get 3 ABC cubes, got {len(p0_abc_cubes)}"
    assert len(p1_abc_cubes) == 3, f"Player 1 should get 3 ABC cubes, got {len(p1_abc_cubes)}"
    results.abc_displayed_p0 = True
    results.abc_displayed_p1 = True
    print("✓ ABC letters displayed for both players")
    
    # Get the specific cube assignments for testing
    p0_cubes = [cube for cube, letter in sorted(p0_abc_cubes)]  # A, B, C cubes for P0
    p1_cubes = [cube for cube, letter in sorted(p1_abc_cubes)]  # A, B, C cubes for P1
    
    print(f"Player 0 will use cubes: {p0_cubes}")
    print(f"Player 1 will use cubes: {p1_cubes}")
    
    print("\n4. COMPLETE ABC SEQUENCE FOR PLAYER 0")
    current_time = 3000
    
    # Simulate Player 0 connecting their ABC cubes in sequence
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p0_cubes[0]}"), payload=Mock(decode=lambda: p0_cubes[1])),
        current_time, mock_sound_manager)
    
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p0_cubes[1]}"), payload=Mock(decode=lambda: p0_cubes[2])),
        current_time, mock_sound_manager)
    
    # Wait for countdown to complete - simulate the polling that happens in the main loop
    countdown_complete = False
    for wait_time in range(current_time + 1000, current_time + 5000, 100):  # Wait up to 4 seconds
        incidents = await cubes_to_game.abc_manager.check_countdown_completion(publish_queue, wait_time)
        if 0 in cubes_to_game._game_started_players:
            countdown_complete = True
            break
    
    assert countdown_complete, "Player 0's countdown should have completed"
    # Check that Player 0's game started
    assert 0 in cubes_to_game._game_started_players, "Player 0 game should be started"
    assert 1 not in cubes_to_game._game_started_players, "Player 1 game should NOT be started"
    results.game_started_p0 = True
    print("✓ Player 0 ABC sequence completed and game started")
    
    print("\n5. SIMULATE LOADING LETTERS")
    current_time = 4000
    
    # Create test tiles for both players
    test_tiles_p0 = [tiles.Tile("X", "0"), tiles.Tile("Y", "1"), tiles.Tile("Z", "2"), 
                     tiles.Tile("A", "3"), tiles.Tile("B", "4"), tiles.Tile("C", "5")]
    test_tiles_p1 = [tiles.Tile("P", "0"), tiles.Tile("Q", "1"), tiles.Tile("R", "2"),
                     tiles.Tile("S", "3"), tiles.Tile("T", "4"), tiles.Tile("U", "5")]
    
    # Clear previous messages
    publish_queue.messages.clear()
    
    # Load rack for both players
    await cubes_to_game.cube_managers[0].load_rack(publish_queue, test_tiles_p0, current_time)
    await cubes_to_game.cube_managers[1].load_rack(publish_queue, test_tiles_p1, current_time)
    
    # Analyze which players got letters
    letter_messages = [msg for msg in publish_queue.messages if 'letter' in msg[0] and msg[1] not in [' ', 'A', 'B', 'C']]
    
    p0_got_letters = any(msg[0].split('/')[1] in ['1', '2', '3', '4', '5', '6'] for msg in letter_messages)
    p1_got_letters = any(msg[0].split('/')[1] in ['11', '12', '13', '14', '15', '16'] for msg in letter_messages)
    
    print(f"Player 0 received letters: {p0_got_letters}")
    print(f"Player 1 received letters: {p1_got_letters}")
    
    # Verify only Player 0 got letters (since only they completed ABC)
    assert p0_got_letters, "Player 0 should receive letters after completing ABC"
    assert not p1_got_letters, "Player 1 should NOT receive letters until completing ABC"
    results.letters_sent_p0 = True
    print("✓ Only Player 0 received letters")
    
    print("\n6. TRY TO COMPLETE ABC SEQUENCE FOR PLAYER 1 (SHOULD FAIL - ABC CLEARED)")
    current_time = 5000
    
    # Clear previous messages
    publish_queue.messages.clear()
    
    # Simulate Player 1 trying to connect their ABC cubes, but ABC state is already cleared
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p1_cubes[0]}"), payload=Mock(decode=lambda: p1_cubes[1])),
        current_time, mock_sound_manager)
    
    await cubes_to_game.handle_mqtt_message(publish_queue,
        Mock(topic=Mock(value=f"cube/right/{p1_cubes[1]}"), payload=Mock(decode=lambda: p1_cubes[2])),
        current_time, mock_sound_manager)
    
    # Check that Player 1 cannot start countdown (ABC state was cleared)
    assert 1 not in cubes_to_game.abc_manager.player_countdown_active, "Player 1 should not be able to start countdown"
    assert not cubes_to_game.abc_manager.abc_start_active, "ABC should no longer be active"
    assert not cubes_to_game.abc_manager.player_abc_cubes, "No ABC assignments should exist"
    print("✓ Player 1 cannot complete ABC after Player 0 finished (ABC state cleared)")
    
    # For this test, we'll simulate Player 1 getting letters via manual game start
    # This demonstrates that the per-player letter loading still works
    print("\n7. MANUALLY START PLAYER 1 GAME TO TEST LETTER LOADING")
    
    # Manually mark Player 1 as started (simulating they completed ABC before it was cleared)
    cubes_to_game._game_started_players.add(1)
    results.game_started_p1 = True
    print("✓ Player 1 game manually started for letter loading test")
    
    print("\n8. VERIFY PLAYER 1 CAN RECEIVE LETTERS WHEN GAME IS STARTED")
    current_time = 6000
    
    # Clear previous messages  
    publish_queue.messages.clear()
    
    # Load rack for Player 1 again
    await cubes_to_game.cube_managers[1].load_rack(publish_queue, test_tiles_p1, current_time)
    
    # Check that Player 1 now gets letters
    letter_messages = [msg for msg in publish_queue.messages if 'letter' in msg[0] and msg[1] not in [' ', 'A', 'B', 'C']]
    p1_got_letters_now = any(msg[0].split('/')[1] in ['11', '12', '13', '14', '15', '16'] for msg in letter_messages)
    
    assert p1_got_letters_now, "Player 1 should receive letters when game is started"
    results.letters_sent_p1 = True
    print("✓ Player 1 receives letters when game is started")
    
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"ABC displayed for Player 0: {results.abc_displayed_p0}")
    print(f"ABC displayed for Player 1: {results.abc_displayed_p1}")
    print(f"Game started for Player 0: {results.game_started_p0}")
    print(f"Game started for Player 1: {results.game_started_p1}")
    print(f"Letters sent to Player 0: {results.letters_sent_p0}")
    print(f"Letters sent to Player 1: {results.letters_sent_p1}")
    
    # Overall test result
    all_passed = all([
        results.abc_displayed_p0,
        results.abc_displayed_p1,
        results.game_started_p0,
        results.game_started_p1,
        results.letters_sent_p0,
        results.letters_sent_p1
    ])
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("Per-player ABC sequence system with simplified clearing logic working correctly!")
        return True
    else:
        print("\n❌ SOME TESTS FAILED!")
        return False

async def main():
    """Run the test."""
    try:
        success = await asyncio.wait_for(test_per_player_abc_sequence(), timeout=TEST_TIMEOUT)
        return 0 if success else 1
    except asyncio.TimeoutError:
        print(f"❌ Test timed out after {TEST_TIMEOUT} seconds")
        return 1
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the test
    exit_code = asyncio.run(main())
    sys.exit(exit_code)