import pytest
from tests.fixtures.game_factory import create_test_game, async_test
import pygame

@async_test
async def test_min_win_score_exit_code():
    """Verify that exit code 10 is returned only when player earns 3 stars."""
    # 1. Test loss case (Score = 99, < 1 star for min_win_score=100)
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=100, stars=True)
    game.scores[0].score = 99
    await game.stop(pygame.time.get_ticks(), exit_code=0)
    assert game.exit_code == 11, "Exit code should be 11 when < 3 stars earned"

    # 2. Test win case (Score = 100 = 3 stars)
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=100, stars=True)
    game.scores[0].score = 100
    await game.stop(pygame.time.get_ticks(), exit_code=0)
    assert game.exit_code == 10, "Exit code should be 10 when 3 stars earned"

    # 3. Test win case (Score = 150 = 3 stars capped)
    game, mqtt, queue = await create_test_game(player_count=1, min_win_score=100, stars=True)
    game.scores[0].score = 150
    await game.stop(pygame.time.get_ticks(), exit_code=0)
    assert game.exit_code == 10, "Exit code should be 10 when 3 stars earned"

@async_test
async def test_min_win_score_invalid():
    """Verify that min_win_score must be non-negative."""
    with pytest.raises(ValueError) as excinfo:
        await create_test_game(player_count=1, min_win_score=-1)
    assert "must be non-negative" in str(excinfo.value)
