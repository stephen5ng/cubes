
import pytest
from unittest.mock import MagicMock, patch
import pygame
from game.components import StarsDisplay, NullStarsDisplay

class MockRackMetrics:
    LETTER_SIZE = 20

@pytest.fixture
def stars_display():
    # Initialize pygame for surface creation
    pygame.init()
    # Mock font rendering to avoid external dependencies if needed
    with patch('pygame.freetype.SysFont'):
        return StarsDisplay(MockRackMetrics())

def test_initial_state(stars_display):
    """Verify stars start empty."""
    assert stars_display._last_filled_count == 0
    assert all(t == -1 for t in stars_display._star_animation_start_ms)
    assert stars_display.num_stars == 3

def test_score_updates(stars_display):
    """Verify stars fill based on score thresholds."""
    # 5 points -> 0 stars
    stars_display.draw(5, now_ms=1000)
    assert stars_display._last_filled_count == 0
    
    # 10 points -> 1 star
    stars_display.draw(10, now_ms=2000)
    assert stars_display._last_filled_count == 1
    assert stars_display._star_animation_start_ms[0] == 2000
    
    # 25 points -> 2 stars
    stars_display.draw(25, now_ms=3000)
    assert stars_display._last_filled_count == 2
    assert stars_display._star_animation_start_ms[1] == 3000
    
    # 50 points -> 3 stars (max)
    stars_display.draw(50, now_ms=4000)
    assert stars_display._last_filled_count == 3
    assert stars_display._star_animation_start_ms[2] == 4000

def test_animation_state(stars_display):
    """Verify animation triggering logic."""
    # Trigger first star
    stars_display.draw(10, now_ms=1000)
    assert stars_display._star_animation_start_ms[0] == 1000
    assert stars_display._needs_redraw is True
    
    # Update during animation
    window = pygame.Surface((100, 100))
    
    # Reset redraw flag to test if update sets it back
    stars_display._needs_redraw = False 
    stars_display.update(window, now_ms=1100)
    
    # Should still be animating (100ms elapsed < 800ms duration)
    assert stars_display._needs_redraw is True
    
    # Update after animation
    stars_display._needs_redraw = False
    stars_display.update(window, now_ms=2000) # 1000ms elapsed > 800ms duration
    
    # Should stop needing redraw
    assert stars_display._needs_redraw is False

def test_null_stars_display():
    """Verify NullStarsDisplay interface works without error."""
    null_display = NullStarsDisplay()
    window = MagicMock()
    
    # specific attributes should not crash
    null_display.draw(100, now_ms=1000)
    null_display.update(window, now_ms=1000)
