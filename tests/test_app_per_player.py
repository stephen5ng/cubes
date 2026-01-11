#!/usr/bin/env python3

import asyncio
import unittest
from unittest.mock import Mock, patch, AsyncMock
from io import StringIO

from core import app
from hardware import cubes_to_game
from hardware.cubes_to_game import state as ctg_state
from hardware.cubes_interface import CubesHardwareInterface
from core import dictionary
from core import tiles
from hardware.cubes_interface import CubesHardwareInterface

class TestAppPerPlayerIntegration(unittest.IsolatedAsyncioTestCase):
    """Test cases for app-level per-player integration."""
    
    async def asyncSetUp(self):
        # Clear global state
        ctg_state._started_players.clear()
        ctg_state._started_cube_sets.clear()
        
        # Create mock dictionary
        mock_open = lambda filename, mode: StringIO("\n".join([
            "test", "word", "abc"
        ]))
        
        self.dictionary = dictionary.Dictionary(3, 6, mock_open)
        self.dictionary.read("sowpods.txt", "bingos.txt")
        
        # Create publish queue
        self.publish_queue = asyncio.Queue()
        
        # Create app instance
        self.app = app.App(self.publish_queue, self.dictionary, CubesHardwareInterface())
        
        # Mock RackManager
        self.app.rack_manager = Mock()
        self.mock_racks = [Mock(), Mock()]
        self.app.rack_manager.get_rack.side_effect = lambda i: self.mock_racks[i]
        
        for i, rack in enumerate(self.mock_racks):
            rack.get_tiles.return_value = [Mock() for _ in range(6)]
            for j, tile in enumerate(rack.get_tiles.return_value):
                tile.tile_id = str(j)
                tile.letter = chr(ord('A') + j)
                
    async def test_load_rack_no_players_started(self):
        """Test app load_rack when no players have started games."""
        with patch.object(cubes_to_game, 'has_player_started_game', return_value=False):
            with patch.object(cubes_to_game, 'load_rack') as mock_load_rack:
                await self.app.load_rack(1000)
                
                # load_rack should not be called for any player
                mock_load_rack.assert_not_called()
                
    async def test_load_rack_only_player_0_started(self):
        """Test app load_rack when only player 0 has started."""
        def mock_has_started(player):
            return player == 0
            
        with patch.object(cubes_to_game, 'has_player_started_game', side_effect=mock_has_started):
            with patch.object(cubes_to_game, 'load_rack') as mock_load_rack:
                mock_load_rack.return_value = asyncio.create_task(asyncio.sleep(0))
                
                await self.app.load_rack(1000)
                
                # load_rack should be called only for player 0
                mock_load_rack.assert_called_once()
                call_args = mock_load_rack.call_args
                self.assertEqual(call_args[0][2], 0)  # player number should be 0
                
    async def test_load_rack_only_player_1_started(self):
        """Test app load_rack when only player 1 has started."""
        def mock_has_started(player):
            return player == 1
            
        with patch.object(cubes_to_game, 'has_player_started_game', side_effect=mock_has_started):
            with patch.object(cubes_to_game, 'load_rack') as mock_load_rack:
                mock_load_rack.return_value = asyncio.create_task(asyncio.sleep(0))
                
                await self.app.load_rack(1000)
                
                # load_rack should be called only for player 1
                mock_load_rack.assert_called_once()
                call_args = mock_load_rack.call_args
                self.assertEqual(call_args[0][2], 1)  # player number should be 1
                
    async def test_load_rack_both_players_started(self):
        """Test app load_rack when both players have started."""
        with patch.object(cubes_to_game, 'has_player_started_game', return_value=True):
            with patch.object(cubes_to_game, 'load_rack') as mock_load_rack:
                mock_load_rack.return_value = asyncio.create_task(asyncio.sleep(0))
                
                await self.app.load_rack(1000)
                
                # load_rack should be called for both players
                self.assertEqual(mock_load_rack.call_count, 2)
                
                # Check that both players 0 and 1 were called
                call_args_list = [call[0][2] for call in mock_load_rack.call_args_list]
                self.assertIn(0, call_args_list)
                self.assertIn(1, call_args_list)
                
    async def test_load_rack_with_correct_tiles(self):
        """Test that load_rack passes correct tiles for each player."""
        with patch.object(cubes_to_game, 'has_player_started_game', return_value=True):
            with patch.object(cubes_to_game, 'load_rack') as mock_load_rack:
                mock_load_rack.return_value = asyncio.create_task(asyncio.sleep(0))
                
                await self.app.load_rack(1000)
                
                # Verify that the correct player's tiles were passed
                self.assertEqual(mock_load_rack.call_count, 2)
                
                # Check player 0 call
                player_0_call = next(call for call in mock_load_rack.call_args_list if call[0][2] == 0)
                self.assertEqual(player_0_call[0][1], self.mock_racks[0].get_tiles())
                
                # Check player 1 call  
                player_1_call = next(call for call in mock_load_rack.call_args_list if call[0][2] == 1)
                self.assertEqual(player_1_call[0][1], self.mock_racks[1].get_tiles())


class TestAppInstanceCreation(unittest.TestCase):
    """Test cases for App instance creation with per-player functionality."""

    def test_app_creation_with_per_player_support(self):
        """Test that App can be created with per-player functionality."""
        mock_publish_queue = Mock()
        mock_dictionary = Mock()

        # Create app instance
        test_app = app.App(mock_publish_queue, mock_dictionary, CubesHardwareInterface())

        # Test that the app was created successfully with expected attributes
        self.assertIsNotNone(test_app)
        self.assertEqual(test_app._publish_queue, mock_publish_queue)
        self.assertEqual(test_app._dictionary, mock_dictionary)


class TestPlayerToCubeSetMapping(unittest.IsolatedAsyncioTestCase):
    """Test cases for player-to-cube-set mapping initialization."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Clear global state
        ctg_state._started_players.clear()
        ctg_state._started_cube_sets.clear()

        # Create mock dictionary
        mock_open = lambda filename, mode: StringIO("\n".join([
            "test", "word", "abc"
        ]))

        self.dictionary = dictionary.Dictionary(3, 6, mock_open)
        self.dictionary.read("sowpods.txt", "bingos.txt")

        # Create publish queue
        self.publish_queue = asyncio.Queue()

        # Create app instance
        self.app = app.App(self.publish_queue, self.dictionary, CubesHardwareInterface())

    async def test_keyboard_start_no_abc(self):
        """Test keyboard start preserves default mapping."""
        # Given: No cube sets started (keyboard mode)
        # _started_cube_sets is empty (cleared in setUp)

        # When: _set_player_to_cube_set_mapping() called
        self.app._set_player_to_cube_set_mapping()

        # Then: Default mapping {0: 0, 1: 1} preserved
        self.assertEqual(self.app._player_to_cube_set[0], 0)
        self.assertEqual(self.app._player_to_cube_set[1], 1)

        # And: _started_players remains empty (keyboard start doesn't populate it)
        self.assertEqual(len(cubes_to_game.get_started_cube_sets()), 0)

    async def test_single_player_cube_set_0_abc(self):
        """Test single player starting on cube set 0."""
        # Given: Cube set 0 completed ABC
        cubes_to_game.add_started_cube_set(0)

        # When: _set_player_to_cube_set_mapping() called
        self.app._set_player_to_cube_set_mapping()

        # Then: Player 0 maps to cube set 0
        self.assertEqual(self.app._player_to_cube_set[0], 0)

        # And: _started_players contains only player 0
        self.assertTrue(cubes_to_game.has_player_started_game(0))
        self.assertFalse(cubes_to_game.has_player_started_game(1))

    async def test_single_player_cube_set_1_abc(self):
        """Test single player starting on cube set 1."""
        # Given: Cube set 1 completed ABC (cubes 11-16)
        cubes_to_game.add_started_cube_set(1)

        # When: _set_player_to_cube_set_mapping() called
        self.app._set_player_to_cube_set_mapping()

        # Then: Player 1 maps to cube set 1 (preserves physical cube set ID)
        self.assertEqual(self.app._player_to_cube_set[1], 1)

        # And: _started_players contains only player 1
        self.assertFalse(cubes_to_game.has_player_started_game(0))
        self.assertTrue(cubes_to_game.has_player_started_game(1))

    async def test_two_players_both_abc(self):
        """Test both players completing ABC."""
        # Given: Both cube sets completed ABC
        cubes_to_game.add_started_cube_set(0)
        cubes_to_game.add_started_cube_set(1)

        # When: _set_player_to_cube_set_mapping() called
        self.app._set_player_to_cube_set_mapping()

        # Then: Player 0→cube set 0, Player 1→cube set 1
        self.assertEqual(self.app._player_to_cube_set[0], 0)
        self.assertEqual(self.app._player_to_cube_set[1], 1)

        # And: _started_players contains both players
        self.assertTrue(cubes_to_game.has_player_started_game(0))
        self.assertTrue(cubes_to_game.has_player_started_game(1))


class TestAppStartIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for the full App.start() flow."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Clear global state
        ctg_state._started_players.clear()
        ctg_state._started_cube_sets.clear()

        # Create mock dictionary with actual rack generation
        mock_open = lambda filename, mode: StringIO("\n".join([
            "test", "word", "abc", "cat", "dog"
        ]))

        self.dictionary = dictionary.Dictionary(3, 6, mock_open)
        self.dictionary.read("sowpods.txt", "bingos.txt")

        # Create publish queue
        self.publish_queue = asyncio.Queue()

        # Create app instance
        self.app = app.App(self.publish_queue, self.dictionary, CubesHardwareInterface())

        # Mock word logger to avoid missing attribute errors
        self.app._word_logger = Mock()
        self.app._word_logger.log_word_formed = Mock()

    async def test_full_start_flow_keyboard(self):
        """Test complete start() flow for keyboard-started game."""
        # Given: No ABC sequence (keyboard start)
        # _started_cube_sets is empty

        # Mock the cubes_to_game functions
        with patch.object(cubes_to_game, 'set_game_running') as mock_set_running:
            with patch.object(cubes_to_game, 'clear_remaining_abc_cubes', new_callable=AsyncMock) as mock_clear_abc:
                with patch.object(cubes_to_game, 'load_rack', new_callable=AsyncMock) as mock_load_rack:
                    with patch.object(cubes_to_game, 'guess_last_tiles', new_callable=AsyncMock) as mock_guess_last:
                        # When: start() is called
                        await self.app.start(1000)

                        # Then: Game running state is set
                        mock_set_running.assert_called_once_with(True)

                        # And: ABC cubes are cleared
                        mock_clear_abc.assert_called_once()

                        # And: Rack is loaded (uses has_player_started_game check, which returns False for keyboard start)
                        # So load_rack won't be called for players in this scenario

                        # And: guess_last_tiles is called for player 0 (based on _player_count=1)
                        self.assertEqual(mock_guess_last.call_count, 1)

                        # And: Default mapping is used
                        self.assertEqual(self.app._player_to_cube_set[0], 0)
                        self.assertEqual(self.app._player_to_cube_set[1], 1)

    async def test_full_start_flow_abc_single_player(self):
        """Test complete start() flow for ABC-started game."""
        # Given: Cube set 0 completed ABC
        cubes_to_game.add_started_cube_set(0)

        # Mock the cubes_to_game functions
        with patch.object(cubes_to_game, 'set_game_running') as mock_set_running:
            with patch.object(cubes_to_game, 'clear_remaining_abc_cubes', new_callable=AsyncMock) as mock_clear_abc:
                with patch.object(cubes_to_game, 'load_rack', new_callable=AsyncMock) as mock_load_rack:
                    with patch.object(cubes_to_game, 'guess_last_tiles', new_callable=AsyncMock) as mock_guess_last:
                        # When: start() is called
                        await self.app.start(1000)

                        # Then: Game running state is set
                        mock_set_running.assert_called_once_with(True)

                        # And: Player 0 is marked as started
                        self.assertTrue(cubes_to_game.has_player_started_game(0))

                        # And: Player 0 maps to cube set 0
                        self.assertEqual(self.app._player_to_cube_set[0], 0)

                        # And: load_rack is called for player 0
                        self.assertEqual(mock_load_rack.call_count, 1)
                        load_call = mock_load_rack.call_args_list[0]
                        self.assertEqual(load_call[0][2], 0)  # cube_set_id
                        self.assertEqual(load_call[0][3], 0)  # player

    async def test_full_start_flow_two_players(self):
        """Test complete start() flow for two-player ABC-started game."""
        # Given: Both cube sets completed ABC
        cubes_to_game.add_started_cube_set(0)
        cubes_to_game.add_started_cube_set(1)
        self.app._player_count = 2

        # Mock the cubes_to_game functions
        with patch.object(cubes_to_game, 'set_game_running'):
            with patch.object(cubes_to_game, 'clear_remaining_abc_cubes', new_callable=AsyncMock):
                with patch.object(cubes_to_game, 'load_rack', new_callable=AsyncMock) as mock_load_rack:
                    with patch.object(cubes_to_game, 'guess_last_tiles', new_callable=AsyncMock) as mock_guess_last:
                        # When: start() is called
                        await self.app.start(1000)

                        # Then: Both players are marked as started
                        self.assertTrue(cubes_to_game.has_player_started_game(0))
                        self.assertTrue(cubes_to_game.has_player_started_game(1))

                        # And: Mappings are correct
                        self.assertEqual(self.app._player_to_cube_set[0], 0)
                        self.assertEqual(self.app._player_to_cube_set[1], 1)

                        # And: load_rack is called for both players
                        self.assertEqual(mock_load_rack.call_count, 2)

                        # And: guess_last_tiles is called for both players
                        self.assertEqual(mock_guess_last.call_count, 2)


class TestAppEdgeCases(unittest.IsolatedAsyncioTestCase):
    """Test edge cases in App behavior."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Clear global state
        ctg_state._started_players.clear()
        ctg_state._started_cube_sets.clear()

        # Create mock dictionary
        mock_open = lambda filename, mode: StringIO("\n".join([
            "test", "word", "abc"
        ]))

        self.dictionary = dictionary.Dictionary(3, 6, mock_open)
        self.dictionary.read("sowpods.txt", "bingos.txt")

        # Create publish queue
        self.publish_queue = asyncio.Queue()

        # Create app instance
        self.app = app.App(self.publish_queue, self.dictionary, CubesHardwareInterface())

        # Mock word logger
        self.app._word_logger = Mock()

    async def test_player_to_cube_set_missing_key_raises_keyerror(self):
        """Test KeyError is raised if mapping is missing (validates fail-fast)."""
        # Given: Invalid state where player 5 is requested but not in mapping
        # The default mapping only has {0: 0, 1: 1}

        # When/Then: Accessing non-existent player raises KeyError
        with self.assertRaises(KeyError):
            _ = self.app._player_to_cube_set[5]

    async def test_accept_new_letter_uses_correct_mapping(self):
        """Test accept_new_letter uses player-to-cube-set mapping correctly for 2 players."""
        # Given: Two players, both completed ABC
        cubes_to_game.add_started_cube_set(0)
        cubes_to_game.add_started_cube_set(1)
        self.app._player_count = 2
        self.app._set_player_to_cube_set_mapping()

        # Create real racks with tiles for both players
        # Configure mock_racks for both players
        # We need to make sure _rack_manager.get_rack() returns these
        self.app.rack_manager = Mock()
        rack0 = tiles.Rack('ABCDEF')
        rack1 = tiles.Rack('GHIJKL')
        self.app.rack_manager.get_rack.side_effect = lambda i: rack0 if i == 0 else rack1
        # Also mock accept_new_letter to return a dummy tile with an ID, as app uses it
        mock_tile = Mock()
        mock_tile.id = "mock_id"
        self.app.rack_manager.accept_new_letter.return_value = mock_tile

        # Mock cubes_to_game.accept_new_letter
        with patch.object(cubes_to_game, 'accept_new_letter', new_callable=AsyncMock) as mock_accept:
            # When: accept_new_letter is called
            await self.app.accept_new_letter('X', 0, 1000)

            # Then: It should be called twice (once per player)
            self.assertEqual(mock_accept.call_count, 2)

            # And: Player 0 should use cube set 0
            player_0_call = next(call for call in mock_accept.call_args_list if call[0][3] == 0)
            self.assertEqual(player_0_call[0][3], 0, "Player 0 should use cube set 0")

            # And: Player 1 should use cube set 1
            player_1_call = next(call for call in mock_accept.call_args_list if call[0][3] == 1)
            self.assertEqual(player_1_call[0][3], 1, "Player 1 should use cube set 1")

    async def test_guess_tiles_uses_correct_cube_set(self):
        """Test guess_tiles routes to correct cube set."""
        # Given: Player 0 on cube set 0
        cubes_to_game.add_started_cube_set(0)
        self.app._set_player_to_cube_set_mapping()

        # Configure mock_racks for player 0
        self.app.rack_manager = Mock()
        rack0 = tiles.Rack('ABCDEF')
        self.app.rack_manager.get_rack.return_value = rack0

        # Mock cubes_to_game functions
        with patch.object(cubes_to_game, 'old_guess', new_callable=AsyncMock):
            with patch.object(cubes_to_game, 'good_guess', new_callable=AsyncMock) as mock_good:
                with patch.object(cubes_to_game, 'bad_guess', new_callable=AsyncMock):
                    # Setup for good guess
                    with patch.object(self.app._score_card, 'is_old_guess', return_value=False):
                        with patch.object(self.app._score_card, 'is_good_guess', return_value=True):
                            with patch.object(self.app._score_card, 'calculate_score', return_value=10):
                                # When: guess_tiles is called for player 0
                                await self.app.guess_tiles(['0', '1', '2'], False, 0, 1000)

                                # Then: good_guess is called with cube set 0
                                self.assertEqual(mock_good.call_count, 1)
                                call_args = mock_good.call_args[0]
                                cube_set_id = call_args[2]
                                self.assertEqual(cube_set_id, 0, "Should use cube set 0 for player 0")


if __name__ == '__main__':
    unittest.main()