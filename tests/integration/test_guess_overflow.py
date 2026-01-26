import pytest
import pygame
from config import game_config
from tests.fixtures.game_factory import create_test_game, async_test


@async_test
async def test_game_does_not_end_on_guess_overflow():
    """Verify that the game continues when guesses overflow the screen."""
    game, mqtt, queue = await create_test_game(player_count=1)

    assert game.running is True

    window = pygame.Surface((game_config.SCREEN_WIDTH, game_config.SCREEN_HEIGHT))
    guesses = []

    for i in range(50):
        word = f"WORD{i}"
        guesses.append(word)
        await game.add_guess(guesses, word, 0, 1000 + i * 100)
        await game.update(window, 1000 + i * 100)

        # Game should stay running
        assert game.running is True, "Game should NOT end on overflow/full"

    assert game.running is True, "Game should NOT end on overflow/full"

    # Ensure calling update again doesn't raise or cause issues
    for i in range(10):
        window.fill((0, 0, 0))
        await game.update(window, 20000 + i * 16)

        # Verify screen has content (not blank)
        has_content = False
        for y in range(30, 100, 10):
            if window.get_at((10, y)) != (0, 0, 0, 255):
                has_content = True
                break
        assert has_content, "Screen should not be blank after overflow"


@async_test
async def test_shrink_on_overflow():
    """Verify that the font shrinks when guesses cause overflow."""
    game, mqtt, queue = await create_test_game(player_count=1)

    initial_font_size = game.guesses_manager.previous_guesses_display.font.size

    # Create enough words to force vertical overflow and trigger resize
    long_guess_words = [f"LINE{i}" for i in range(60)]

    await game.add_guess(long_guess_words, "LASTWORD", 0, 0)

    window = pygame.Surface((game_config.SCREEN_WIDTH, game_config.SCREEN_HEIGHT))
    await game.update(window, 100)

    current_size = game.guesses_manager.previous_guesses_display.font.size
    assert current_size < initial_font_size, f"Font size should have shrunk from {initial_font_size}, got {current_size}"
