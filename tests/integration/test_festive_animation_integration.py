
import pytest
import asyncio
from tests.fixtures.game_factory import create_test_game, async_test

@async_test
async def test_festive_animation_on_game_over():
    """Verify that festive animation starts only after game over."""
    game, mqtt, queue = await create_test_game(player_count=1)
    
    # Start game, this ensures game.running is True
    await game.start_cubes(0)
    
    # Manually set rack tiles to make "TEST" a valid guess
    from core.tiles import Tile
    rack = game._app.rack_manager.get_rack(0)
    rack.set_tiles([Tile(id=str(i), letter=l) for i, l in enumerate("TEST!!")])

    # Add a guess so there is something to animate
    game._app.add_guess("TEST", 0)
    await asyncio.sleep(0.1)
    
    # Provide a surface for rendering
    import pygame
    window = pygame.Surface((800, 600))
    
    # 1. Update during game running
    renderer = game.guesses_manager.previous_guesses_display._text_rect_renderer
    initial_time = renderer.animation_time
    
    # We must invoke game.update or guesses_manager.update directly
    # game.guesses_manager.update is called by game.update
    await game.update(window, 0)
    
    # Should NOT have animated because game.running is True
    assert game.running is True
    assert renderer.animation_time == initial_time
    
    # 2. Stop game (Game Over)
    await game.stop(0)
    assert game.running is False
    
    # 3. Update after game over
    await game.update(window, 0)
    
    # Should HAVE animated because game.running is False and we are within 15s
    assert renderer.animation_time > initial_time
    
    # 4. Advance time > 15s
    # stop(0) set stop_time_s to 0.0.
    # So we need to call update with time > 15000 ms
    
    current_time = renderer.animation_time
    await game.update(window, 16000) # 16 seconds
    
    # Should stop animating
    assert renderer.animation_time == current_time
