
import pytest
from unittest.mock import MagicMock, patch
import pygame
from game.components import StarsDisplay, NullStarsDisplay
from config.game_config import SCREEN_WIDTH

class MockRackMetrics:
    LETTER_SIZE = 20

@pytest.fixture
def stars_display():
    # Initialize pygame for surface creation
    pygame.init()
    # Mock font rendering to avoid external dependencies if needed
    with patch('pygame.freetype.SysFont'):
        # Use 30 as min_win_score so 10 points = 1 star
        return StarsDisplay(MockRackMetrics(), min_win_score=30, sound_manager=None)

def test_initial_state(stars_display):
    """Verify stars start empty."""
    assert stars_display._last_filled_count == 0
    assert all(t == -1 for t in stars_display._star_animation_start_ms)
    assert stars_display.num_stars == 3
    assert stars_display._heartbeat_start_ms == -1
    
    # Verify centered position
    # pos = [int(SCREEN_WIDTH/2 - total_width/2), 0]
    total_width = stars_display.surface.get_width()
    expected_x = int(SCREEN_WIDTH/2 - total_width/2)
    assert stars_display.pos[0] == expected_x

def test_score_updates(stars_display):
    """Verify stars fill based on score thresholds."""
    # 5 points -> 0 stars (score < 30/3 = 10)
    assert stars_display.draw(5, now_ms=1000) == 0
    assert stars_display._last_filled_count == 0
    
    # 10 points -> 1 star
    assert stars_display.draw(10, now_ms=2000) == 1
    assert stars_display._last_filled_count == 1
    assert stars_display._star_animation_start_ms[0] == 2000
    
    # 20 points -> 2 stars
    assert stars_display.draw(20, now_ms=3000) == 2
    assert stars_display._last_filled_count == 2
    assert stars_display._star_animation_start_ms[1] == 3000
    
    # 30 points -> 3 stars (max)
    assert stars_display.draw(30, now_ms=4000) == 3
    assert stars_display._last_filled_count == 3
    assert stars_display._star_animation_start_ms[2] == 4000

def test_tada_sound():
    """Verify tada sound is played when 3rd star is earned."""
    pygame.init()
    mock_sound_manager = MagicMock()
    with patch('pygame.freetype.SysFont'):
        # Use 30 as min_win_score so 10 points = 1 star
        display = StarsDisplay(MockRackMetrics(), min_win_score=30, sound_manager=mock_sound_manager)
        
    # Mock starspin length to 1 second
    mock_sound_manager.get_starspin_length.return_value = 1.0
    
    # Earn 2 stars
    display.draw(20, now_ms=1000)
    mock_sound_manager.play_tada.assert_not_called()
    mock_sound_manager.play_starspin.assert_called_once()
    
    # Reset mocks for next step
    mock_sound_manager.play_starspin.reset_mock()
    
    # Earn 3rd star
    display.draw(30, now_ms=2000)
    # Tada should NOT play immediately (scheduled for 2000 + 800ms = 2800ms, when 3rd star finishes spinning)
    mock_sound_manager.play_tada.assert_not_called()
    mock_sound_manager.play_starspin.assert_called_once()

    # Update before tada scheduled time
    window = MagicMock()
    display.update(window, now_ms=2400)
    mock_sound_manager.play_tada.assert_not_called()

    # Update after scheduled time (tada and blink animation start)
    display.update(window, now_ms=2900)
    mock_sound_manager.play_tada.assert_called_once()
    assert display._heartbeat_start_ms == 2900
    
    # Earn more points (already has 3 stars)
    display.draw(40, now_ms=3000)
    mock_sound_manager.play_tada.assert_called_once()

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
