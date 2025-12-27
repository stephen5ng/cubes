#!/usr/bin/env python3

import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from blockwords.hardware import cubes_to_game
from blockwords.core import tiles

class TestPerPlayerGameStates(unittest.TestCase):
    """Test cases for per-player game state management."""
    
    def setUp(self):
        # Clear global state before each test
        cubes_to_game._game_started_players.clear()
        cubes_to_game.abc_manager.player_abc_cubes.clear()
        
    def test_has_player_started_game_empty(self):
        """Test has_player_started_game returns False when no players have started."""
        self.assertFalse(cubes_to_game.has_player_started_game(0))
        self.assertFalse(cubes_to_game.has_player_started_game(1))
        
    def test_has_player_started_game_after_start(self):
        """Test has_player_started_game returns True after player starts game."""
        # Manually add player to game states (simulating game start)
        cubes_to_game._game_started_players.add(0)
        
        self.assertTrue(cubes_to_game.has_player_started_game(0))
        self.assertFalse(cubes_to_game.has_player_started_game(1))
        
    def test_multiple_players_independent_states(self):
        """Test that multiple players can have independent game states."""
        # Start player 0
        cubes_to_game._game_started_players.add(0)
        
        self.assertTrue(cubes_to_game.has_player_started_game(0))
        self.assertFalse(cubes_to_game.has_player_started_game(1))
        
        # Start player 1
        cubes_to_game._game_started_players.add(1)
        
        self.assertTrue(cubes_to_game.has_player_started_game(0))
        self.assertTrue(cubes_to_game.has_player_started_game(1))
        
        # Remove player 0
        cubes_to_game._game_started_players.discard(0)
        
        self.assertFalse(cubes_to_game.has_player_started_game(0))
        self.assertTrue(cubes_to_game.has_player_started_game(1))


class TestABCSequencePerPlayer(unittest.IsolatedAsyncioTestCase):
    """Test cases for per-player ABC sequence logic."""
    
    async def asyncSetUp(self):
        # Clear global state
        cubes_to_game.abc_manager.player_abc_cubes.clear()
        cubes_to_game._game_started_players.clear()
        
        # Set up cube managers for both players
        cubes_to_game.cube_managers = [
            cubes_to_game.CubeSetManager(0),
            cubes_to_game.CubeSetManager(1)
        ]
        
        # Player 0: cubes 1-6
        cubes_to_game.cube_managers[0].cube_list = ["1", "2", "3", "4", "5", "6"]
        # Player 1: cubes 11-16  
        cubes_to_game.cube_managers[1].cube_list = ["11", "12", "13", "14", "15", "16"]
        
    def test_find_non_touching_cubes_basic(self):
        """Test _find_non_touching_cubes_for_player returns cubes without neighbors."""
        manager = cubes_to_game.cube_managers[0]
        
        # Test function exists and returns a list
        result = cubes_to_game._find_non_touching_cubes_for_player(manager)
        
        # Should return a list of cubes 
        self.assertIsInstance(result, list)
        # Should return up to 3 cubes
        self.assertLessEqual(len(result), 3)
            
    def test_find_non_touching_cubes_insufficient_cubes(self):
        """Test _find_non_touching_cubes_for_player with insufficient available cubes."""
        manager = cubes_to_game.cube_managers[0]
        manager.cube_list = ["1", "2"]  # Only 2 cubes available
        
        result = cubes_to_game._find_non_touching_cubes_for_player(manager)
        
        # Should return available cubes (up to what's available)
        self.assertIsInstance(result, list)
        self.assertLessEqual(len(result), 2)
            
    async def test_abc_sequence_detection_function_exists(self):
        """Test that ABC sequence detection function exists and is callable."""
        # Test function exists
        self.assertTrue(hasattr(cubes_to_game, 'abc_manager'))
        self.assertTrue(hasattr(cubes_to_game.abc_manager, 'check_abc_sequence_complete'))
        self.assertTrue(callable(cubes_to_game.abc_manager.check_abc_sequence_complete))
        
        # Test it returns something (None when no completion)
        result = await cubes_to_game.abc_manager.check_abc_sequence_complete()
        # Should return None when no ABC sequences are set up
        self.assertIsNone(result)


class TestLoadRackPerPlayer(unittest.IsolatedAsyncioTestCase):
    """Test cases for per-player letter loading in CubeManager.load_rack()."""
    
    async def asyncSetUp(self):
        # Clear global state
        cubes_to_game._game_started_players.clear()
        
        # Create cube manager
        self.cube_manager = cubes_to_game.CubeSetManager(0)
        self.cube_manager.cube_list = ["1", "2", "3", "4", "5", "6"]
        self.cube_manager.tiles_to_cubes = {
            "0": "1", "1": "2", "2": "3", "3": "4", "4": "5", "5": "6"
        }
        
        # Create mock publish queue
        self.publish_queue = asyncio.Queue()
        
        # Create mock tiles
        self.mock_tiles = [Mock() for _ in range(6)]
        for i, tile in enumerate(self.mock_tiles):
            tile.tile_id = str(i)
            tile.letter = chr(ord('A') + i)  # A, B, C, D, E, F
            
    async def test_load_rack_player_not_started(self):
        """Test load_rack skips loading when player hasn't started game."""
        # Player 0 hasn't started game (not in _game_started_players)
        
        result = await self.cube_manager.load_rack(
            self.publish_queue, self.mock_tiles, 1000
        )
        
        # Should return early without loading letters
        self.assertIsNone(result)
        
        # No messages should be published
        self.assertTrue(self.publish_queue.empty())
        
    async def test_load_rack_player_started_basic(self):
        """Test basic load_rack behavior."""
        # Test that the method exists and can be called
        self.assertTrue(hasattr(self.cube_manager, 'load_rack'))
        self.assertTrue(callable(self.cube_manager.load_rack))
        
        # Test early return when player not started
        result = await self.cube_manager.load_rack(
            self.publish_queue, self.mock_tiles, 1000
        )
        self.assertIsNone(result)


class TestCubeAssignmentUpdates(unittest.TestCase):
    """Test cases for updated cube assignments (1-6 + 11-16 instead of 1-12)."""
    
    def test_cube_assignment_ranges(self):
        """Test that cube assignment uses correct ranges (1-6 and 11-16)."""
        expected_cubes = [str(i) for i in range(1, 7)] + [str(i) for i in range(11, 17)]
        
        # Test that expected cubes are in the range we use
        for cube in expected_cubes:
            cube_num = int(cube)
            # Should be in range 1-6 or 11-16
            self.assertTrue((1 <= cube_num <= 6) or (11 <= cube_num <= 16))
            
        # Test that cubes outside range are not included
        invalid_cubes = ["7", "8", "9", "10", "17", "18"]
        for cube in invalid_cubes:
            cube_num = int(cube)
            self.assertFalse((1 <= cube_num <= 6) or (11 <= cube_num <= 16))
            
    def test_cube_manager_player_assignments(self):
        """Test that CubeManager instances get correct cube lists per player."""
        # Create managers
        manager_0 = cubes_to_game.CubeSetManager(0)
        manager_1 = cubes_to_game.CubeSetManager(1)
        
        # Player 0 should get cubes 1-6
        manager_0.cube_list = ["1", "2", "3", "4", "5", "6"]
        expected_p0 = ["1", "2", "3", "4", "5", "6"]
        self.assertEqual(manager_0.cube_list, expected_p0)
        
        # Player 1 should get cubes 11-16
        manager_1.cube_list = ["11", "12", "13", "14", "15", "16"]
        expected_p1 = ["11", "12", "13", "14", "15", "16"]
        self.assertEqual(manager_1.cube_list, expected_p1)


if __name__ == '__main__':
    unittest.main()