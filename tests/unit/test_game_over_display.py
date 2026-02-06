import unittest
from unittest.mock import MagicMock, patch
import pygame
from ui.game_over_display import GameOverDisplay
from config.game_config import GOOD_GUESS_COLOR, BAD_GUESS_COLOR

class TestGameOverDisplay(unittest.TestCase):
    def setUp(self):
        # Patch pygame.freetype.SysFont
        self.patcher = patch('pygame.freetype.SysFont')
        self.mock_font_class = self.patcher.start()
        self.mock_font_instance = self.mock_font_class.return_value
        
        # Setup render return values
        self.mock_text_surface = MagicMock()
        self.mock_text_rect = pygame.Rect(0, 0, 100, 50)
        self.mock_text_surface.get_rect.return_value = self.mock_text_rect
        self.mock_font_instance.render.return_value = (self.mock_text_surface, self.mock_text_rect)
        
        self.display = GameOverDisplay()
        
    def tearDown(self):
        self.patcher.stop()

    def test_draw_won(self):
        window = MagicMock()
        # Mock screen dimensions in config if needed, but they are imported constants.
        # Let's patch config matching usage in module
        with patch('ui.game_over_display.SCREEN_WIDTH', 200), \
             patch('ui.game_over_display.SCREEN_HEIGHT', 150):
            
            self.display.draw(window, won=True)
            
            # Verify render called with correct text and color
            self.mock_font_instance.render.assert_called_with("CONGRATS!", GOOD_GUESS_COLOR)
            
            # Verify blit position
            # (200 - 100) // 2 = 50
            # (150 - 50) // 2 = 50
            window.blit.assert_called_with(self.mock_text_surface, (50, 50))

    def test_draw_lost(self):
        window = MagicMock()

        with patch('ui.game_over_display.SCREEN_WIDTH', 200), \
             patch('ui.game_over_display.SCREEN_HEIGHT', 150):

            self.display.draw(window, won=False)

            # Verify render called twice for "GAME" and "OVER"
            self.assertEqual(self.mock_font_instance.render.call_count, 2)
            # First call for "GAME"
            self.mock_font_instance.render.assert_any_call("GAME", BAD_GUESS_COLOR)
            # Second call for "OVER"
            self.mock_font_instance.render.assert_any_call("OVER", BAD_GUESS_COLOR)

if __name__ == '__main__':
    unittest.main()
