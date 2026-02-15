"""Unit tests for coordination.py orchestration layer."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from hardware.cubes_to_game import coordination
from hardware.cubes_to_game import state
from hardware.cubes_to_game.cube_set_manager import CubeSetManager


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""

    def test_get_all_cube_ids(self):
        """Should return all valid cube IDs (1-6 for P0, 11-16 for P1)."""
        cube_ids = coordination._get_all_cube_ids()
        
        # Should have 12 IDs total
        self.assertEqual(len(cube_ids), 12)
        
        # P0 cubes: 1-6
        for i in range(1, 7):
            self.assertIn(str(i), cube_ids)
        
        # P1 cubes: 11-16
        for i in range(11, 17):
            self.assertIn(str(i), cube_ids)

    def test_has_received_initial_neighbor_reports_empty(self):
        """Should return False when no neighbor reports received."""
        # Clear all neighbor data
        for manager in coordination.cube_set_managers:
            manager.cubes_to_neighbors = {}
        
        self.assertFalse(coordination._has_received_initial_neighbor_reports())

    def test_has_received_initial_neighbor_reports_has_data(self):
        """Should return True when at least one manager has neighbor reports."""
        # Clear all first
        for manager in coordination.cube_set_managers:
            manager.cubes_to_neighbors = {}
        
        # Add neighbor data to first manager
        coordination.cube_set_managers[0].cubes_to_neighbors = {"1": "2"}
        
        self.assertTrue(coordination._has_received_initial_neighbor_reports())


class TestPublishLetter(unittest.IsolatedAsyncioTestCase):
    """Test _publish_letter helper."""

    async def test_publish_letter_puts_to_queue(self):
        """Should publish letter to correct topic with retain."""
        queue = asyncio.Queue()
        
        await coordination._publish_letter(queue, "A", "5", 1000)
        
        topic, message, retain, timestamp = await queue.get()
        self.assertEqual(topic, "cube/5/letter")
        self.assertEqual(message, "A")
        self.assertTrue(retain)
        self.assertEqual(timestamp, 1000)


class TestLetterLock(unittest.IsolatedAsyncioTestCase):
    """Test letter_lock functionality."""

    async def test_letter_lock_first_lock(self):
        """First lock should publish lock message."""
        queue = asyncio.Queue()
        state.locked_cubes.clear()
        
        # Mock tiles_to_cubes mapping
        coordination.cube_set_managers[0].tiles_to_cubes = {"tile1": "3"}
        
        result = await coordination.letter_lock(queue, 0, "tile1", 1000)
        
        self.assertTrue(result)
        self.assertEqual(state.locked_cubes[0], "3")
        
        # Should have published lock message
        topic, message, retain, timestamp = await queue.get()
        self.assertEqual(topic, "cube/3/lock")
        self.assertEqual(message, "1")
        self.assertTrue(retain)

    async def test_letter_lock_same_cube_twice(self):
        """Locking same cube twice should return False."""
        queue = asyncio.Queue()
        state.locked_cubes.clear()
        
        coordination.cube_set_managers[0].tiles_to_cubes = {"tile1": "3"}
        
        # First lock
        result1 = await coordination.letter_lock(queue, 0, "tile1", 1000)
        self.assertTrue(result1)
        await queue.get()  # Clear queue
        
        # Second lock of same tile
        result2 = await coordination.letter_lock(queue, 0, "tile1", 2000)
        self.assertFalse(result2)
        self.assertTrue(queue.empty())  # No new messages

    async def test_letter_lock_unlock_previous(self):
        """Locking new cube should unlock previous cube."""
        queue = asyncio.Queue()
        state.locked_cubes.clear()
        
        coordination.cube_set_managers[0].tiles_to_cubes = {"tile1": "3", "tile2": "4"}
        
        # Lock first cube
        await coordination.letter_lock(queue, 0, "tile1", 1000)
        await queue.get()  # Clear queue
        
        # Lock second cube
        result = await coordination.letter_lock(queue, 0, "tile2", 2000)
        self.assertTrue(result)
        self.assertEqual(state.locked_cubes[0], "4")
        
        # Should have unlocked first cube
        topic1, message1, retain1, timestamp1 = await queue.get()
        self.assertEqual(topic1, "cube/3/lock")
        self.assertIsNone(message1)
        
        # Should have locked second cube
        topic2, message2, retain2, timestamp2 = await queue.get()
        self.assertEqual(topic2, "cube/4/lock")
        self.assertEqual(message2, "1")

    async def test_letter_lock_none_unlocks(self):
        """Passing None for tile_id should unlock current cube."""
        queue = asyncio.Queue()
        state.locked_cubes.clear()
        
        coordination.cube_set_managers[0].tiles_to_cubes = {"tile1": "3"}
        
        # Lock first
        await coordination.letter_lock(queue, 0, "tile1", 1000)
        await queue.get()  # Clear queue
        
        # Unlock with None
        result = await coordination.letter_lock(queue, 0, None, 2000)
        self.assertTrue(result)
        self.assertIsNone(state.locked_cubes[0])
        
        # Should have unlocked
        topic, message, retain, timestamp = await queue.get()
        self.assertEqual(topic, "cube/3/lock")
        self.assertIsNone(message)


class TestUnlockAllLetters(unittest.IsolatedAsyncioTestCase):
    """Test unlock_all_letters functionality."""

    async def test_unlock_all_letters_empty(self):
        """Unlocking when nothing is locked should do nothing."""
        queue = asyncio.Queue()
        state.locked_cubes.clear()
        
        await coordination.unlock_all_letters(queue, 1000)
        
        self.assertTrue(queue.empty())
        self.assertEqual(len(state.locked_cubes), 0)

    async def test_unlock_all_letters_multiple(self):
        """Should unlock all locked cubes across all cube sets."""
        queue = asyncio.Queue()
        state.locked_cubes.clear()
        
        # Lock cubes for both players
        state.locked_cubes[0] = "3"
        state.locked_cubes[1] = "12"
        
        await coordination.unlock_all_letters(queue, 1000)
        
        # Should have cleared state
        self.assertEqual(len(state.locked_cubes), 0)
        
        # Should have unlocked both
        messages = []
        while not queue.empty():
            messages.append(await queue.get())
        
        self.assertEqual(len(messages), 2)
        topics = {msg[0] for msg in messages}
        self.assertIn("cube/3/lock", topics)
        self.assertIn("cube/12/lock", topics)


class TestBulkOperations(unittest.IsolatedAsyncioTestCase):
    """Test bulk operations."""

    async def test_clear_all_borders(self):
        """Should clear borders on all cubes."""
        queue = asyncio.Queue()
        
        # Mock cube lists
        coordination.cube_set_managers[0].cube_list = ["1", "2", "3"]
        coordination.cube_set_managers[1].cube_list = ["11", "12", "13"]
        
        await coordination.clear_all_borders(queue, 1000)
        
        # Should have messages for all 6 cubes
        messages = []
        while not queue.empty():
            messages.append(await queue.get())
        
        self.assertEqual(len(messages), 6)
        
        # All should use ":" to clear borders
        for topic, message, retain, timestamp in messages:
            self.assertTrue(topic.endswith("/border"))
            self.assertEqual(message, ":")
            self.assertTrue(retain)

    async def test_clear_all_letters(self):
        """Should clear letters on all cubes with space character."""
        queue = asyncio.Queue()
        
        coordination.cube_set_managers[0].cube_list = ["1", "2"]
        coordination.cube_set_managers[1].cube_list = ["11", "12"]
        
        await coordination.clear_all_letters(queue, 1000)
        
        messages = []
        while not queue.empty():
            messages.append(await queue.get())
        
        self.assertEqual(len(messages), 4)
        
        # All should use space to clear
        for topic, message, retain, timestamp in messages:
            self.assertTrue(topic.endswith("/letter"))
            self.assertEqual(message, " ")
            self.assertTrue(retain)

    async def test_clear_remaining_abc_cubes(self):
        """Should clear ABC cubes and remove from tracking."""
        queue = asyncio.Queue()
        
        # Set up ABC assignments
        state.abc_manager.player_abc_cubes = {
            0: {"A": "1", "B": "2", "C": "3"},
            1: {"A": "11", "B": "12", "C": "13"}
        }
        
        await coordination.clear_remaining_abc_cubes(queue, 1000)
        
        # Should have cleared tracking
        self.assertEqual(len(state.abc_manager.player_abc_cubes), 0)
        
        # Should have sent clear messages
        messages = []
        while not queue.empty():
            messages.append(await queue.get())
        
        self.assertEqual(len(messages), 6)  # 3 cubes per player


class TestGuessFeedback(unittest.IsolatedAsyncioTestCase):
    """Test guess feedback functions."""

    async def test_good_guess_green_border(self):
        """Good guess should set green border."""
        queue = asyncio.Queue()
        
        # Mock flash_guess to avoid actual flashing
        with patch.object(coordination.cube_set_managers[0], 'flash_guess', new_callable=AsyncMock):
            await coordination.good_guess(queue, ["tile1"], 0, 0, 1000)
        
        self.assertEqual(coordination.cube_set_managers[0].border_color, "0x07E0")  # Green

    async def test_old_guess_yellow_border(self):
        """Old guess should set yellow border."""
        await coordination.old_guess(None, ["tile1"], 0, 0)
        
        self.assertEqual(coordination.cube_set_managers[0].border_color, "0xFFE0")  # Yellow

    async def test_bad_guess_white_border(self):
        """Bad guess should set white border."""
        await coordination.bad_guess(None, ["tile1"], 0, 0)
        
        self.assertEqual(coordination.cube_set_managers[0].border_color, "0xFFFF")  # White


class TestABCManagement(unittest.TestCase):
    """Test ABC start management."""

    def test_is_any_player_in_countdown_delegates(self):
        """Should delegate to abc_manager."""
        with patch.object(state.abc_manager, 'is_any_player_in_countdown', return_value=True):
            result = coordination.is_any_player_in_countdown()
            self.assertTrue(result)


class TestABCManagementAsync(unittest.IsolatedAsyncioTestCase):
    """Test async ABC start management functions."""

    async def test_activate_abc_start_if_ready_not_ready(self):
        """Should not activate when game is running."""
        queue = asyncio.Queue()
        
        # Mock game running
        with patch.object(state, 'get_game_running', return_value=True):
            with patch.object(state.abc_manager, 'assign_abc_letters_to_available_players', new_callable=AsyncMock) as mock_assign:
                await coordination.activate_abc_start_if_ready(queue, 1000)
                
                # Should not have called assign
                mock_assign.assert_not_called()

    async def test_activate_abc_start_if_ready_no_neighbors(self):
        """Should not activate when no neighbor reports received."""
        queue = asyncio.Queue()
        
        # Clear neighbor data
        for manager in coordination.cube_set_managers:
            manager.cubes_to_neighbors = {}
        
        with patch.object(state, 'get_game_running', return_value=False):
            with patch.object(state.abc_manager, 'assign_abc_letters_to_available_players', new_callable=AsyncMock) as mock_assign:
                await coordination.activate_abc_start_if_ready(queue, 1000)
                
                mock_assign.assert_not_called()

    async def test_activate_abc_start_if_ready_success(self):
        """Should activate when conditions are met."""
        queue = asyncio.Queue()

        # Set up conditions
        coordination.cube_set_managers[0].cubes_to_neighbors = {"1": "2"}

        with patch.object(state, 'get_game_running', return_value=False):
            with patch.object(state.abc_manager, 'assign_abc_letters_to_available_players', new_callable=AsyncMock) as mock_assign:
                await coordination.activate_abc_start_if_ready(queue, 1000)

                # Should have called assign
                mock_assign.assert_called_once()

    async def test_set_game_end_time_resets_abc_in_game_on_mode(self):
        """ABC manager should be reset when game ends in game_on mode (min_win_score > 0)."""
        # Set up ABC manager with active state
        state.abc_manager.abc_start_active = True
        state.abc_manager.player_abc_cubes = {0: {"A": "1", "B": "2", "C": "3"}}

        # Call set_game_end_time with min_win_score > 0 (game_on mode)
        state.set_game_end_time(1000, min_win_score=90)

        # Verify ABC manager was reset
        self.assertFalse(state.abc_manager.abc_start_active)
        self.assertEqual(state.abc_manager.player_abc_cubes, {})

    async def test_set_game_end_time_preserves_abc_in_normal_mode(self):
        """ABC manager should NOT be reset in normal mode (min_win_score = 0)."""
        # Set up ABC manager with active state
        state.abc_manager.abc_start_active = True
        state.abc_manager.player_abc_cubes = {0: {"A": "1", "B": "2", "C": "3"}}

        # Call set_game_end_time with min_win_score = 0 (normal mode)
        state.set_game_end_time(1000, min_win_score=0)

        # Verify ABC manager was NOT reset
        self.assertTrue(state.abc_manager.abc_start_active)
        self.assertEqual(state.abc_manager.player_abc_cubes, {0: {"A": "1", "B": "2", "C": "3"}})

    async def test_activate_abc_start_blocked_after_game_on_ends(self):
        """ABC should not be activated after game_on mode ends, even if conditions are met."""
        queue = asyncio.Queue()

        # Set up conditions: game not running, has neighbor reports
        state._game_running = False
        coordination.cube_set_managers[0].cubes_to_neighbors = {"1": "2"}

        # Set game_on_mode_ended flag (simulating game_on mode game end)
        state.game_on_mode_ended = True

        with patch.object(state.abc_manager, 'assign_abc_letters_to_available_players', new_callable=AsyncMock) as mock_assign:
            await coordination.activate_abc_start_if_ready(queue, 1000)

            # Should NOT have called assign because game_on_mode_ended is True
            mock_assign.assert_not_called()

        # Verify flag is set
        self.assertTrue(state.game_on_mode_ended)

    def tearDown(self):
        """Clean up global state after tests."""
        state.reset_game_on_mode_ended()


class TestMQTTMessageHandler(unittest.IsolatedAsyncioTestCase):
    """Test MQTT message handling."""

    def tearDown(self):
        """Clean up global state after tests."""
        state._started_players.clear()
        state._started_cube_sets.clear()
        state.cube_to_cube_set.clear()
        state.reset_game_on_mode_ended()

    async def test_handle_mqtt_message_right_edge(self):
        """Should handle right-edge neighbor messages."""
        queue = asyncio.Queue()

        # Set up cube mapping
        state.cube_to_cube_set["3"] = 0
        state._started_players.clear()
        state._started_players.add(0)
        
        # Mock message
        message = MagicMock()
        message.topic.value = "cube/right/3"
        message.payload.decode.return_value = "4"
        
        # Mock process_neighbor_cube to return word tiles
        with patch.object(coordination.cube_set_managers[0], 'process_neighbor_cube', return_value=[["tile1"]]):
            with patch.object(coordination, 'guess_tiles', new_callable=AsyncMock):
                await coordination.handle_mqtt_message(queue, message, 1000, None)

    async def test_handle_mqtt_message_abc_completion(self):
        """Should check ABC completion after right-edge update."""
        queue = asyncio.Queue()
        sound_manager = MagicMock()

        state.cube_to_cube_set["3"] = 0
        state._started_players.clear()
        state._started_players.add(0)
        state.abc_manager.abc_start_active = True
        
        message = MagicMock()
        message.topic.value = "cube/right/3"
        message.payload.decode.return_value = "4"
        
        with patch.object(coordination.cube_set_managers[0], 'process_neighbor_cube', return_value=[]):
            with patch.object(coordination, 'guess_tiles', new_callable=AsyncMock):
                with patch.object(state.abc_manager, 'check_abc_sequence_complete', new_callable=AsyncMock, return_value=0) as mock_check:
                    with patch.object(state.abc_manager, 'handle_abc_completion', new_callable=AsyncMock) as mock_handle:
                        await coordination.handle_mqtt_message(queue, message, 1000, sound_manager)
                        
                        # Should have checked and handled completion
                        mock_check.assert_called_once()
                        mock_handle.assert_called_once()


if __name__ == '__main__':
    unittest.main()
