import pytest
import pygame
from unittest.mock import Mock, patch
from tests.fixtures.game_factory import create_test_game, async_test
from rendering.animations import LETTER_SOURCE_YELLOW

@async_test
async def test_yellow_zone_gradient_drawing():
    """Verify that the yellow zone gradient is drawn when there is a gap."""
    game, _, _ = await create_test_game(visual=False)
    
    # Mock strategies to return fixed values so update() doesn't move them
    # DescentStrategy.update(now_ms, height) -> int
    game.letter.descent_strategy.update = Mock(return_value=150)
    # The yellow tracker uses its own strategy
    game.yellow_tracker.descent_strategy.update = Mock(return_value=50)
    
    # Setup mock window
    window = Mock(spec=pygame.Surface)
    window.blit = Mock()
    
    # Ensure game is running
    game.running = True
    
    # Set up positions to create a gap
    initial_y = game.letter_source.initial_y
    
    # Pre-set values just in case (though update call will overwrite from strategy)
    game.yellow_tracker.start_fall_y = 50
    game.letter.start_fall_y = 150
    
    # We need to mock pygame.transform.smoothscale to avoid actual scaling logic issues in mock environment
    # and to verify it's called
    with patch('pygame.transform.smoothscale') as mock_scale:
        mock_scaled_surface = Mock(spec=pygame.Surface)
        mock_scale.return_value = mock_scaled_surface
        
        now_ms = 1000
        await game.update(window, now_ms)
        
        # Verify strategies were called
        assert game.letter.descent_strategy.update.called
        assert game.yellow_tracker.descent_strategy.update.called
        
        # Verify gradient was scaled
        assert mock_scale.called
        
        # Verify blit was called with the scaled surface
        # The exact position should be (x, top)
        # top = min(y_yellow, y_red) = initial_y + 50
        expected_top = initial_y + 50
        
        blit_calls = window.blit.call_args_list
        found_call = False
        for call in blit_calls:
            args, _ = call
            if args[0] == mock_scaled_surface:
                pos = args[1]
                # print(f"DEBUG: Found call with pos={pos}, expected_top={expected_top}")
                if pos[1] == expected_top:
                    found_call = True
                    break
        
        assert found_call, f"Gradient surface should be blitted at the correct vertical position {expected_top}"

@async_test
async def test_yellow_zone_no_drawing_when_no_gap():
    """Verify that the yellow zone is NOT drawn when lines overlap or are inverted (height 0)."""
    game, _, _ = await create_test_game(visual=False)
    window = Mock(spec=pygame.Surface)
    window.blit = Mock()
    game.running = True
    
    # Yellow tracker IS updated before drawing, so we mock its strategy return value
    game.yellow_tracker.descent_strategy.update = Mock(return_value=100)
    
    # Letter IS NOT updated before drawing, so we must set its current state
    game.letter.start_fall_y = 100
    # We also mock its strategy for consistency when it does update later
    game.letter.descent_strategy.update = Mock(return_value=100)
    
    with patch('pygame.transform.smoothscale') as mock_scale:
        await game.update(window, 1000)
        
        # Should not scale (create gradient) if height is 0
        assert not mock_scale.called
