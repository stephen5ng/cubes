import pytest
from tests.fixtures.game_factory import create_test_game, async_test
import pygame

@async_test
async def test_min_win_score_exit_code():
    """Verify that exit code 10 is returned when score >= min_win_score."""
    # 1. Test failure case (Score < 100)
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=100)
    game.scores[0].score = 99
    await game.stop(pygame.time.get_ticks(), exit_code=0)
    assert game.exit_code == 0, "Exit code should remain 0 when score < min_win_score"
    
    # 2. Test success case (Score >= 100)
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=100)
    game.scores[0].score = 100
    await game.stop(pygame.time.get_ticks(), exit_code=0)
    assert game.exit_code == 10, "Exit code should be 10 when score >= min_win_score"

    # 3. Test success case (Score > 100)
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=100)
    game.scores[0].score = 150
    await game.stop(pygame.time.get_ticks(), exit_code=0)
    assert game.exit_code == 10, "Exit code should be 10 when score > min_win_score"

@async_test
async def test_min_win_score_invalid():
    """Verify that min_win_score must be positive."""
    with pytest.raises(ValueError) as excinfo:
        await create_test_game(player_count=1, min_win_score=0)
    assert "must be positive" in str(excinfo.value)
