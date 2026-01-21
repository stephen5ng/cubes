import pytest
import asyncio
from typing import Tuple

from game.game_state import Game
from game.components import Shield
from config import game_config
from tests.fixtures.game_factory import (
    create_test_game,
    create_shield,
    async_test,
    run_until_condition,
    advance_frames,
    advance_seconds,
    advance_milliseconds,
    get_mock_time
)

@pytest.mark.timed
@pytest.mark.fast
@async_test
async def test_yellow_descends_slower_than_red():
    """Verify yellow line descends slower than the red line (letter start_fall_y)."""
    # Create game in timed mode with specific duration (60s)
    duration_s = 60
    game, fake_mqtt, queue = await create_test_game(descent_mode="timed", timed_duration_s=duration_s)
    
    # Reset running to False to force a full start() which initializes start_time_s
    game.running = False
    await game.start_cubes(now_ms=0)

    # Advance time by 10 seconds
    await advance_seconds(game, queue, 10)
    
    red_y = game.letter.start_fall_y
    # PositionTracker tracks start_fall_y which is the visual Y
    yellow_y = game.yellow_tracker.start_fall_y
    
    # Yellow line should be higher (smaller Y) than red line
    # Because yellow duration is 3x game duration, so it moves 1/3 as fast
    assert yellow_y < red_y, f"Yellow line ({yellow_y}) should be above Red line ({red_y})"
    
    # Check ratio is roughly 1/3. Allow some margin for frame timing differences.
    ratio = yellow_y / red_y if red_y > 0 else 0
    assert 0.2 < ratio < 0.45, f"Yellow/Red ratio {ratio:.2f} should be approx 0.33"

    # Advance another 10 seconds
    await advance_seconds(game, queue, 10)
    
    red_y_2 = game.letter.start_fall_y
    yellow_y_2 = game.yellow_tracker.start_fall_y
    
    assert yellow_y_2 > yellow_y, f"Yellow line should descend. y1={yellow_y}, y2={yellow_y_2}"
    assert red_y_2 > red_y, "Red line should continue descending" 
    assert yellow_y_2 < red_y_2, "Yellow line still above Red line"


@pytest.mark.timed
@pytest.mark.shield
@pytest.mark.fast
@async_test
async def test_red_line_pushback_on_yellow_line():
    """Verify red line gets pushed back to yellow line on collision at the red line."""
    # Use 60s duration to allow setup time
    game, fake_mqtt, queue = await create_test_game(descent_mode="timed", timed_duration_s=60)
    game.running = False
    await game.start_cubes(now_ms=0)

    # Advance until lines have moved down significantly (30s)
    await advance_seconds(game, queue, 30)
    
    current_red_y = game.letter.start_fall_y
    current_yellow_y = game.yellow_tracker.start_fall_y
    
    assert current_red_y > current_yellow_y + 20, "Red line needs to be significantly below yellow line for this test"

    # 1. Force letter to be exactly at start_fall_y using _apply_descent
    # This prepares the internal state (current_fall_start_y) so it sticks to the red line.
    setup_ms = 30000  # 30 seconds in milliseconds
    game.letter._apply_descent(current_red_y, setup_ms)

    # 2. Place a shield there so it collides.
    shield_x = game.letter.pos[0]
    letter_bottom = game.letter.get_screen_bottom_y()

    shield = create_shield("PUSH", x=shield_x, y=letter_bottom - 5)
    game.shields.append(shield)

    # 3. Run update at next frame
    now_ms = setup_ms + 16
    
    import pygame
    window = pygame.display.get_surface()
    if window is None:
         window = pygame.Surface((game_config.SCREEN_WIDTH, game_config.SCREEN_HEIGHT))

    incidents = await game.update(window, now_ms)
    
    # Check results
    assert "shield_letter_collision" in incidents, "Collision should have been detected"
    assert "red_line_pushed_to_yellow" in incidents, "Should have triggered red line pushback"
    
    # Verify Red Line is now at Yellow Line
    expected_red = game.yellow_tracker.start_fall_y
    assert abs(game.letter.start_fall_y - expected_red) < 2, \
        f"Red line ({game.letter.start_fall_y}) should be reset to Yellow line ({expected_red})"


@pytest.mark.timed
@pytest.mark.fast
@async_test
async def test_timed_game_ends_at_duration():
    """Verify timed game ends automatically when duration is reached."""
    # Use 5s duration for faster test
    duration_s = 5
    game, fake_mqtt, queue = await create_test_game(descent_mode="timed", timed_duration_s=duration_s)

    game.running = False
    await game.start_cubes(now_ms=0)
    assert game.running

    import pygame
    window = pygame.display.get_surface()
    if window is None:
        window = pygame.Surface((game_config.SCREEN_WIDTH, game_config.SCREEN_HEIGHT))

    # Verify game is running at start (0ms elapsed, letter at top)
    await game.update(window, 0)
    assert game.running, "Game should be running at start"

    # Fast forward past the duration end
    # Note: In timed mode, floor collision also ends game with exit_code=10,
    # so game may end via floor OR duration - both are valid "win" conditions
    game._test_time_provider.advance((duration_s + 1) * 1000)

    await game.update(window, game._test_time_provider.get_ticks())

    assert not game.running, "Game should have ended after duration expired"
    assert game.exit_code == 10, f"Game should end with exit_code 10 (Win), got {game.exit_code}"
