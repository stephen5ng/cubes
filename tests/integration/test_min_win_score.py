import pytest
from tests.fixtures.game_factory import create_test_game, async_test
import pygame

@async_test
async def test_min_win_score_exit_code():
    """Verify that exit code 10 is returned when score >= min_win_score."""
    # Create game with min_win_score=100
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=100)
    
    # 1. Test failure case (Score < 100)
    game.scores[0].score = 99
    # Simulate stopping the game normally
    await game.stop(pygame.time.get_ticks(), exit_code=0)
    
    assert game.exit_code == 0, "Exit code should remain 0 when score < min_win_score"
    
    # Reset game state for next check (or just check the logic by restarting/resetting)
    # For simplicity, we can just call stop again with a higher score since stop() sets exit_code
    
    # 2. Test success case (Score >= 100)
    game.scores[0].score = 100
    await game.stop(pygame.time.get_ticks(), exit_code=0)
    
    assert game.exit_code == 10, "Exit code should be 10 when score >= min_win_score"

    # 3. Test success case (Score > 100)
    game.scores[0].score = 150
    await game.stop(pygame.time.get_ticks(), exit_code=0)
    
    assert game.exit_code == 10, "Exit code should be 10 when score > min_win_score"

@async_test
async def test_min_win_score_disabled():
    """Verify that exit code is NOT modified when min_win_score is 0 (disabled)."""
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=0)
    
    game.scores[0].score = 1000
    await game.stop(pygame.time.get_ticks(), exit_code=0)
    
    assert game.exit_code == 0, "Exit code should remain 0 when min_win_score is disabled"
