
import pytest
import asyncio
from tests.fixtures.game_factory import create_test_game, async_test
from game.components import Shield
# from config import game_config # Unused now

@async_test
async def test_game_ends_at_winning_score():
    """Verify that the game stops when a player reaches WINNING_SCORE."""
    # Create game with explicit winning score
    TARGET_SCORE = 100
    game, mqtt, queue = await create_test_game(player_count=1, winning_score=TARGET_SCORE)
    
    # 1. Set initial score to just below winning
    game.scores[0].score = TARGET_SCORE - 10
    
    # Verify game is running
    assert game.running is True
    
    # 2. Add a score that pushes it over the limit
    # We simulate this by creating a shield that is about to collide with the letter
    now_ms = 1000
    # Letter is at some Y position. 
    # Shield moves UP. Letter moves DOWN.
    # game.update handles collisions.
    # To ensure collision, we place shield effectively AT the letter's expected position.
    
    # Create the shield first so we can close over it
    shield = Shield(game.rack_metrics.get_rect().topleft, "WIN", 10, 0, now_ms)

    # Monkeypatch shield.update to force its position to a collision state
    def force_collision_update(window, now_ms):
        # Force shield to be at top of screen (0) determines rect.y
        shield.rect = pygame.Rect(0, 0, 10, 10)
        shield.pos = [0, 0]
        
    shield.update = force_collision_update
    game.shields.append(shield)
    
    # Ensure letter is low enough to collide (below top of screen)
    game.letter.pos[1] = 100 

    # 3. specific update to trigger collision
    import pygame
    window = pygame.Surface((100, 100))
    await game.update(window, now_ms + 100)
    
    # 4. Verify game stopped
    assert game.running is False
    assert game.scores[0].score >= TARGET_SCORE
