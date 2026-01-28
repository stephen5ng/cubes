import pytest
import pygame
from tests.fixtures.game_factory import create_test_game, async_test
from rendering.animations import LetterSource

@async_test
async def test_spawn_line_animation_direction():
    """Verify spawn line animation trail appears on correct side based on movement direction."""
    # Setup
    game, _, _ = await create_test_game(visual=False)
    spawn_source = game.spawn_source
    window = pygame.Surface((800, 600))
    now_ms = 0
    
    initial_base_y = spawn_source.initial_y
    
    # 1. Simulate Descent (Moving Down)
    # Move down by 50 pixels
    move_amount = 50
    game.letter.start_fall_y += move_amount
    now_ms += 100
    
    spawn_source.update(window, now_ms)
    
    # Verify State
    assert spawn_source.moving_down is True, "Should be moving down"
    assert spawn_source.height > LetterSource.MIN_HEIGHT, "Should have animation trail"
    
    # When moving down, trail should be above the line to show traversed space
    # pos[1] is the top-left of the drawn surface
    # The actual line is at bottom of surface.
    # Logic in code: y_pos = initial_y + start_fall_y - height
    expected_y = initial_base_y + game.letter.start_fall_y - spawn_source.height
    assert spawn_source.pos[1] == expected_y, "Trail should be above line on descent"

    # Reset animation state by letting it finish (fast forward time)
    now_ms += 2000
    spawn_source.update(window, now_ms)
    assert spawn_source.height == LetterSource.MIN_HEIGHT
    
    # 2. Simulate Push-back (Moving Up)
    # Move up by 30 pixels
    move_up_amount = 30
    current_fall_y = game.letter.start_fall_y
    game.letter.start_fall_y -= move_up_amount
    now_ms += 100
    
    spawn_source.update(window, now_ms)
    
    # Verify State
    assert spawn_source.moving_down is False, "Should be moving up"
    assert spawn_source.height > LetterSource.MIN_HEIGHT, "Should have animation trail"
    
    # When moving up, trail should be below the line to show recovered space
    # Logic in code: y_pos = initial_y + start_fall_y
    # (Without subtracting height)
    expected_y_up = initial_base_y + game.letter.start_fall_y
    assert spawn_source.pos[1] == expected_y_up, "Trail should be below line on ascent"
