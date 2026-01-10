"""Single Player Integration Tests

Tests core gameplay mechanics for single player mode:
- Scoring
- Guess tracking
- Rack management updates
"""
import pytest
from tests.fixtures.game_factory import create_test_game, async_test, wait_for_guess_processing

@async_test
async def test_single_player_p0_scoring():
    """Verify Player 0 can score words and update game state."""
    game, _mqtt, queue = await create_test_game()
    
    # Initial state
    assert game.scores[0].score == 0
    
    # Simulate scoring "CAT" (3 points)
    # Note: stage_guess bypasses rack validation, which is fine for testing Game effects
    await game.stage_guess(3, "CAT", 0, 1000)
    
    # Wait for score to update and guess to be registered
    await wait_for_guess_processing(game, queue, player=0, expected_score=3, expected_word="CAT")
    
    # Verify score update
    assert game.scores[0].score == 3
    
    # Verify guess recorded
    assert game.guesses_manager.guess_to_player["CAT"] == 0

@async_test
async def test_single_player_p1_scoring():
    """Verify Player 1 can score words independently (requires multi-player setup)."""
    # Initialize with enough players
    game, _mqtt, queue = await create_test_game(player_count=2)
    
    # Initial state
    assert game.scores[1].score == 0
    
    # Simulate scoring "DOGS" (4 points) for P1
    await game.stage_guess(4, "DOGS", 1, 1000)
    
    # Wait for score and guess
    await wait_for_guess_processing(game, queue, player=1, expected_score=4, expected_word="DOGS")
    
    # Verify score update
    assert game.scores[1].score == 4
    
    # Verify guess recorded for correct player
    assert game.guesses_manager.guess_to_player["DOGS"] == 1
