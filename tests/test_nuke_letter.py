"""Tests for the special "nuke" letter behavior."""
import pytest
import pygame
import pygame.freetype
from unittest.mock import Mock, patch
from game.letter import Letter
from rendering.metrics import RackMetrics

@pytest.fixture
def letter_setup():
    """Setup Letter instance for testing."""
    pygame.init()
    pygame.freetype.init()
    pygame.mixer.init()

    rack_metrics = RackMetrics()
    font = rack_metrics.font
    output_logger = Mock()
    letter_beeps = [pygame.mixer.Sound("sounds/bounce.wav")]

    letter = Letter(
        font=font,
        initial_y=0,
        rack_metrics=rack_metrics,
        output_logger=output_logger,
        letter_beeps=letter_beeps
    )
    # Set dimensions for predictable testing
    letter.width = 30
    letter.height = 100

    yield letter
    pygame.quit()

class TestNukeLetterBehavior:
    """Test custom logic for the '!!!!!!' nuke letter."""
    
    def test_nuke_alignment_force_lock(self, letter_setup):
        """The nuke letter should force position to the rack's left edge (x coordinate)."""
        letter = letter_setup
        
        # 1. Start normal update
        letter.letter = "A"
        letter.start(now_ms=0)
        
        # Manipulate state to be mid-animation (fraction_complete != 1.0)
        letter.next_column_move_time_ms = 1000
        # This would normally calculate a position based on easing
        # We don't care about the specific A position, just that it uses standard logic
        
        # 2. Switch to Nuke Letter
        letter.letter = "!!!!!!"
        
        # 3. Update position calculation
        # This calls _calculate_position internally
        letter.draw(now_ms=500)
        
        # ASSERTIONS
        # Position should be exactly the rack's x
        expected_x = letter.rack_metrics.get_rect().x
        assert letter.pos[0] == expected_x
        
        # Fraction complete should be forced to 1.0 (no oscillation)
        assert letter.fraction_complete == 1.0
        assert letter.fraction_complete_eased == 1.0

    def test_nuke_custom_surface_rendering(self, letter_setup):
        """The nuke letter should create a surface spanning the entire rack width."""
        letter = letter_setup # type: Letter
        letter.letter = "!!!!!!"
        
        # Replace the real font with a mock because we can't patch C-extension methods like 'render_to'
        mock_font = Mock()
        # Ensure render_to returns None to match signature
        mock_font.render_to.return_value = None
        letter.font = mock_font
        
        letter.draw(now_ms=0)
        
        # Verify the surface dimensions
        # Should match rack width
        expected_width = letter.rack_metrics.get_rect().width
        assert letter.surface.get_width() == expected_width
        
        # Verify it's a transparency-enabled surface
        assert letter.surface.get_flags() & pygame.SRCALPHA
        
        # Verify render_to was called 6 times (once per slot)
        assert mock_font.render_to.call_count == 6
        
        # Verify arguments of calls to ensure "!" was rendered
        # args: (surf, dest, text, fgcolor)
        for call_args in mock_font.render_to.call_args_list:
            args, _ = call_args
            # args[2] is the text string
            assert args[2] == "!"
