#!/usr/bin/env python3

import asyncio
import unittest
from unittest.mock import Mock, patch, AsyncMock
from io import StringIO

import app
import cubes_to_game
import dictionary
import tiles

class TestAppPerPlayerIntegration(unittest.IsolatedAsyncioTestCase):
    """Test cases for app-level per-player integration."""
    
    async def asyncSetUp(self):
        # Clear global state
        cubes_to_game._game_started_players.clear()
        
        # Create mock dictionary
        mock_open = lambda filename, mode: StringIO("\n".join([
            "test", "word", "abc"
        ]))
        
        self.dictionary = dictionary.Dictionary(3, 6, mock_open)
        self.dictionary.read("sowpods.txt", "bingos.txt")
        
        # Create publish queue
        self.publish_queue = asyncio.Queue()
        
        # Create app instance
        self.app = app.App(self.publish_queue, self.dictionary)
        
        # Mock player racks
        self.app._player_racks = [Mock(), Mock()]
        for i, rack in enumerate(self.app._player_racks):
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
                self.assertEqual(player_0_call[0][1], self.app._player_racks[0].get_tiles())
                
                # Check player 1 call  
                player_1_call = next(call for call in mock_load_rack.call_args_list if call[0][2] == 1)
                self.assertEqual(player_1_call[0][1], self.app._player_racks[1].get_tiles())


class TestAppInstanceCreation(unittest.TestCase):
    """Test cases for App instance creation with per-player functionality."""
    
    def test_app_creation_with_per_player_support(self):
        """Test that App can be created with per-player functionality."""
        mock_publish_queue = Mock()
        mock_dictionary = Mock()
        
        # Create app instance 
        test_app = app.App(mock_publish_queue, mock_dictionary)
        
        # Test that the app was created successfully with expected attributes
        self.assertIsNotNone(test_app)
        self.assertEqual(test_app._publish_queue, mock_publish_queue)
        self.assertEqual(test_app._dictionary, mock_dictionary)


if __name__ == '__main__':
    unittest.main()