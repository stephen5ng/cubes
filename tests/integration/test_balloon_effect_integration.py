
import pytest
import asyncio
from tests.fixtures.game_factory import create_test_game, async_test

@async_test
async def test_balloon_effect_on_game_win():
    """Verify that balloon effect starts only after game over (win)."""
    game, mqtt, queue = await create_test_game(player_count=1)
    
    # Start game
    await game.start_cubes(0)
    
    # Manually set rack tiles
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
    await game.update(window, 0)
    
    # Should NOT have balloon effect because game.running is True
    assert game.running is True
    assert not game.balloon_effects
    
    # 2. Stop game (Game Over - WIN)
    await game.stop(0, exit_code=10)
    assert game.running is False
    
    # 3. Update after game over
    await game.update(window, 0)
    
    # Should HAVE balloon effect because it is a WIN
    assert game.balloon_effects
    # Check that balloons correspond to the guess "TEST"
    assert len(game.balloon_effects[0].balloons) == 1


@async_test
async def test_no_balloon_effect_on_loss():
    """Verify that balloon effect DOES NOT start on loss (exit_code != 10)."""
    game, mqtt, queue = await create_test_game(player_count=1)
    
    await game.start_cubes(0)
    
    # Manually set rack tiles
    from core.tiles import Tile
    rack = game._app.rack_manager.get_rack(0)
    rack.set_tiles([Tile(id=str(i), letter=l) for i, l in enumerate("TEST!!")])

    # Add a guess
    game._app.add_guess("TEST", 0)
    await asyncio.sleep(0.1)
    
    import pygame
    window = pygame.Surface((800, 600))
    
    # 1. Stop game (Game Over - LOSS/NUKE)
    await game.stop(0, exit_code=11)
    assert game.running is False
    
    # 2. Update after game over
    await game.update(window, 0)
    
    # Should NOT have balloon effect
    assert not game.balloon_effects
    # Should have Melt Effect
    assert game.melt_effect is not None
