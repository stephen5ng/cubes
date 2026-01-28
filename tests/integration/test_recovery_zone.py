import pytest
import pygame
from unittest.mock import Mock, patch
from tests.fixtures.game_factory import create_test_game, async_test
from rendering.animations import LETTER_SOURCE_RECOVERY

@async_test
async def test_recovery_zone_gradient_drawing():
    """Verify that the recovery zone gradient IS drawn using tracker positions."""
    game, _, _ = await create_test_game(visual=False)
    
    # Mock strategies
    game.letter.descent_strategy.update = Mock(return_value=150)
    game.recovery_tracker.descent_strategy.update = Mock(return_value=50)
    
    # Setup mock window
    window = Mock(spec=pygame.Surface)
    window.blit = Mock()
    
    # Ensure game is running
    game.running = True
    
    # Manually set strategies starting values for the initial read (before update)
    # The game loop calls update() on strategies, but also reads them.
    # Actually, `update` updates the tracker, then we read tracker.
    game.letter.start_fall_y = 150
    
    # Mock pygame.transform.smoothscale
    with patch('pygame.transform.smoothscale') as mock_scale:
        mock_scaled_surface = Mock(spec=pygame.Surface)
        mock_scale.return_value = mock_scaled_surface
        
        await game.update(window, 1000)
        
        # Verify strategies were called
        assert game.letter.descent_strategy.update.called
        assert game.recovery_tracker.descent_strategy.update.called
        
        # Verify gradient was drawn
        assert mock_scale.called
        
        # Verify position
        # y_recovery = spawn_source.initial_y + 50
        # y_spawn = spawn_source.initial_y + 150
        # top = min(y_recovery, y_spawn) -> spawn_source.initial_y + 50
        initial_y = game.spawn_source.initial_y
        expected_top = initial_y + 50
        
        found_call = False
        for call in window.blit.call_args_list:
            args, _ = call
            if args[0] == mock_scaled_surface:
                pos = args[1]
                if abs(pos[1] - expected_top) < 1:  # allow float tolerance
                    found_call = True
                    break
        
        assert found_call, f"Gradient should be drawn at y={expected_top}"
