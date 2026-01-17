import pytest
from unittest.mock import MagicMock, patch
from tests.fixtures.game_factory import create_test_game, async_test
from ui.guess_display import PreviousGuessesManager
from rendering import text_renderer as textrect
import pygame

@async_test
async def test_overflow_does_not_stop_game():
    """Verify that an extreme overflow (TextRectException) does not stop the game."""
    game, mqtt, queue = await create_test_game(player_count=1)
    
    # Patch resize so it doesn't create new display instances (and doesn't fix overflow)
    game.guesses_manager.resize = MagicMock()
    
    # Patch the display's add_guess method to always raise TextRectException
    # This simulates a situation where content won't fit no matter what
    failing_mock = MagicMock(side_effect=textrect.TextRectException("Forced Overflow"))
    game.guesses_manager.previous_guesses_display.add_guess = failing_mock
    
    # Add a guess
    await game.add_guess(["prev"], "guess", 0, 0)
    
    # Check that game is still running
    # If exception was raised, game would have crashed (stopped execution flow or raised out)
    assert game.running is True, "Game should not have stopped on overflow exception"
    
    # Verify our mock was called (multiple times due to retries)
    assert failing_mock.call_count >= 5, "Should have retried multiple times before giving up"
    
    await game.stop(0)
