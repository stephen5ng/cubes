
import pytest
import asyncio
from unittest.mock import patch, mock_open, MagicMock
from tests.fixtures.game_factory import create_test_game, async_test
from hardware import cubes_to_game
from config import game_config
from game.letter import GuessType

@async_test
async def test_game_start_initialization():
    """Verify that starting the game initializes components."""
    game, mqtt, queue = await create_test_game(player_count=1)
    await game.start_cubes(0) # Ensure game loop is active
    
    # Modify state
    game.scores[0].score = 100
    game.racks[0].guess_type = GuessType.GOOD # Set to non-default
    
    # Stop and Start again
    await game.stop(0, exit_code=0)
    await game.start_cubes(0)
    
    # Assertions
    assert game.scores[0].score == 0
    assert game.racks[0].guess_type == GuessType.BAD # Should reset to default
    assert game.running is True

@async_test
async def test_game_stop_cleanup():
    """Verify that stopping the game triggers cleanup."""
    with patch('hardware.cubes_interface.CubesHardwareInterface.unlock_all_letters') as mock_unlock, \
         patch('hardware.cubes_interface.CubesHardwareInterface.clear_all_borders') as mock_clear:
        
        game, mqtt, queue = await create_test_game(player_count=1)
        await game.start_cubes(0)
        
        # We need to manually stop the game
        await game.stop(0, exit_code=0)
        
        # Verify calls
        mock_unlock.assert_called()
        mock_clear.assert_called()
        assert game.running is False

@async_test
async def test_game_end_logging():
    """Verify that game end logs duration and score."""
    m_open = mock_open()
    
    with patch('builtins.open', m_open):
        game, mqtt, queue = await create_test_game(player_count=1)
        await game.start_cubes(0) # initializes start_time_s
        
        # Play a bit to set start time
        game.start_time_s = 100
        game.scores[0].score = 50
        
        await game.stop(200000, 0) # 200s
        
        # Verify file write
        m_open.assert_called_with("output/durationlog.csv", "a")
        handle = m_open()
        # Duration = 200 - 100 = 100.
        # But now_s = now_ms / 1000. 
        # stop(200000) -> 200s. duration = 200 - 100 = 100.0
        handle.write.assert_called_with("50,100.0\n")

@async_test
async def test_multiple_game_sessions():
    """Verify running multiple games in sequence."""
    game, mqtt, queue = await create_test_game(player_count=1)
    await game.start_cubes(0)
    
    # Game 1
    assert game.running is True
    game.scores[0].score = 10
    await game.stop(0, 0)
    assert game.running is False
    
    # Game 2
    await game.start_cubes(0)
    assert game.running is True
    assert game.scores[0].score == 0 # Should be reset
    
    # Game 3 (stop and start)
    await game.stop(0, 0)
    await game.start_cubes(0)
    assert game.running is True

@async_test
async def test_game_start_clears_abc_tracking():
    """Verify that starting a game removes players from ABC tracking."""
    # Patch the class imported in game_factory
    with patch('tests.fixtures.game_factory.CubesHardwareInterface.remove_player_from_abc_tracking') as mock_remove:
        # Also need to patch clear_remaining_abc_cubes to avoid real calls
        with patch('tests.fixtures.game_factory.CubesHardwareInterface.clear_remaining_abc_cubes'):
            game, mqtt, queue = await create_test_game(player_count=1)

            # create_test_game sets game.running=True manually without calling app.start()
            # We must force a start sequence to trigger the logic under test.
            game.running = False
            await game.start_cubes(0)

            mock_remove.assert_called_with(0)

@async_test
async def test_game_stop_resets_effects():
    """Verify that stopping the game resets melt and balloon effects."""
    from rendering.melt_effect import MeltEffect
    from rendering.balloon_effect import BalloonEffect

    game, mqtt, queue = await create_test_game(player_count=1)
    await game.start_cubes(0)

    # Simulate effects being active (as would happen during game over)
    game.melt_effect = MagicMock(spec=MeltEffect)
    game.balloon_effects = [MagicMock(spec=BalloonEffect), MagicMock(spec=BalloonEffect)]

    # Stop the game
    await game.stop(0, exit_code=11)  # Loss exit code

    # Verify effects are reset
    assert game.melt_effect is None
    assert game.balloon_effects == []
