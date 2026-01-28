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
async def test_recovery_descends_slower_than_spawn():
    """Verify recovery line descends slower than the spawn line (letter start_fall_y)."""
    # Create game in timed mode with specific duration (60s)
    duration_s = 60
    game, fake_mqtt, queue = await create_test_game(descent_mode="timed", descent_duration_s=duration_s)
    
    # Reset running to False to force a full start() which initializes start_time_s
    game.running = False
    await game.start_cubes(now_ms=0)

    # Advance time by 10 seconds
    await advance_seconds(game, queue, 10)
    
    spawn_y = game.letter.start_fall_y
    # PositionTracker tracks start_fall_y which is the visual Y
    recovery_y = game.recovery_tracker.start_fall_y
    
    # Recovery line should be higher (smaller Y) than spawn line
    # Because recovery duration is 3x game duration, so it moves 1/3 as fast
    assert recovery_y < spawn_y, f"Recovery line ({recovery_y}) should be above Spawn line ({spawn_y})"
    
    # Check ratio is roughly 1/3. Allow some margin for frame timing differences.
    ratio = recovery_y / spawn_y if spawn_y > 0 else 0
    assert 0.2 < ratio < 0.45, f"Recovery/Spawn ratio {ratio:.2f} should be approx 0.33"

    # Advance another 10 seconds
    await advance_seconds(game, queue, 10)
    
    spawn_y_2 = game.letter.start_fall_y
    recovery_y_2 = game.recovery_tracker.start_fall_y
    
    assert recovery_y_2 > recovery_y, f"Recovery line should descend. y1={recovery_y}, y2={recovery_y_2}"
    assert spawn_y_2 > spawn_y, "Spawn line should continue descending" 
    assert recovery_y_2 < spawn_y_2, "Recovery line still above Spawn line"


@pytest.mark.timed
@pytest.mark.shield
@pytest.mark.fast
@async_test
async def test_spawn_line_pushback_on_recovery_line():
    """Verify spawn line gets pushed back to recovery line on collision at the spawn line."""
    # Use 60s duration to allow setup time
    game, fake_mqtt, queue = await create_test_game(descent_mode="timed", descent_duration_s=60)
    game.running = False
    await game.start_cubes(now_ms=0)

    # Advance until lines have moved down significantly (30s)
    await advance_seconds(game, queue, 30)
    
    current_spawn_y = game.letter.start_fall_y
    current_recovery_y = game.recovery_tracker.start_fall_y
    
    assert current_spawn_y > current_recovery_y + 20, "Spawn line needs to be significantly below recovery line for this test"

    # 1. Force letter to be exactly at start_fall_y using _apply_descent
    # This prepares the internal state (current_fall_start_y) so it sticks to the spawn line.
    setup_ms = 30000  # 30 seconds in milliseconds
    game.letter._apply_descent(current_spawn_y, setup_ms)

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
    assert "spawn_line_pushed_to_recovery" in incidents, "Should have triggered spawn line pushback"
    
    # Verify Spawn Line is now at Recovery Line
    expected_spawn = game.recovery_tracker.start_fall_y
    assert abs(game.letter.start_fall_y - expected_spawn) < 2, \
        f"Spawn line ({game.letter.start_fall_y}) should be reset to Recovery line ({expected_spawn})"



