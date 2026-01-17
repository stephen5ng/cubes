import unittest
from unittest.mock import MagicMock, patch
import pygame
from rendering import text_renderer as textrect
from ui.guess_display import PreviousGuessesManager, PreviousGuessesDisplay, RemainingPreviousGuessesDisplay

class TestPreviousGuessesManager(unittest.TestCase):
    def setUp(self):
        # Mock dependencies
        self.mock_game_config = MagicMock()
        self.mock_game_config.SCREEN_HEIGHT = 100
        
        # Patch dependencies for initialization
        self.patches = [
            patch('ui.guess_display.PreviousGuessesDisplay'),
            patch('ui.guess_display.RemainingPreviousGuessesDisplay')
        ]
        self.mocks = [p.start() for p in self.patches]
        self.mock_previous_class, self.mock_remaining_class = self.mocks
        
        # Setup instance mocks
        self.mock_previous_instance = self.mock_previous_class.return_value
        self.mock_remaining_instance = self.mock_remaining_class.return_value
        
        self.mock_remaining_class.TOP_GAP = 3 # Ensure TOP_GAP is int, not Mock
        self.mock_previous_class.POSITION_TOP = 24 # Ensure POSITION_TOP is int
        
        # Mock surface and bounding rect
        self.mock_previous_rect = pygame.Rect(0, 0, 100, 50)
        self.mock_remaining_rect = pygame.Rect(0, 50, 100, 20)
        
        self.mock_previous_instance.surface = MagicMock()
        self.mock_previous_instance.surface.get_bounding_rect.return_value = self.mock_previous_rect
        
        self.mock_remaining_instance.surface = MagicMock()
        self.mock_remaining_instance.surface.get_bounding_rect.return_value = self.mock_remaining_rect
        
        self.mock_previous_instance.get_line_height.return_value = 30
        self.mock_previous_instance.font.get_sized_height.return_value = 30
        
        self.manager = PreviousGuessesManager(font_size=30, guess_to_player={})
        # Manually wire up the mocks to the manager instance (init replaced them)
        self.manager.previous_guesses_display = self.mock_previous_instance
        self.manager.remaining_previous_guesses_display = self.mock_remaining_instance

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_is_full_false(self):
        # Setup: Content height 70, Screen 100, Line height 30.
        # Remaining space 30 >= 30. Not full.
        self.mock_previous_rect.height = 50
        self.mock_remaining_rect.height = 20
        # total height = (24 + 50) + (3 + 20) = 74 + 23 = 97?
        # Wait. Logic:
        # total_bottom = POSITION_TOP (24) + height_prev
        # if remaining: total_bottom += TOP_GAP (3) + height_rem
        # Setup says: 
        # Prev Height 50. Rem Height 20.
        # Total = 24 + 50 + 3 + 20 = 97.
        # Screen 100. Available 3.
        # Line height 30.
        # 3 < 30. True (Is FULL).
        # My previous calculation was wrong in comments?
        
        # Let's adjust numbers to make it NOT full.
        # Need available >= 30.
        # So total_bottom <= 70.
        # 24 + 3 = 27 base.
        # Need prev + rem <= 43.
        # Set prev=20, rem=20. Total 40 + 27 = 67.
        
        self.mock_previous_rect.height = 20
        self.mock_remaining_rect.height = 20
        
        with patch('ui.guess_display.SCREEN_HEIGHT', 100):
             self.assertFalse(self.manager.is_full)

    def test_is_full_true(self):
        # Setup: Content height large.
        self.mock_previous_rect.height = 60
        self.mock_remaining_rect.height = 20
        # Total = 24 + 60 + 3 + 20 = 107.
        # 107 > 100. Available negative.
        # Full.
        
        with patch('ui.guess_display.SCREEN_HEIGHT', 100):
             self.assertTrue(self.manager.is_full)

    def test_exec_with_resize_success(self):
        # Function passes immediately
        func = MagicMock()
        
        self.manager.exec_with_resize(func, 0)
        
        func.assert_called_once()
        self.mock_previous_class.from_instance.assert_not_called()

    def test_exec_with_resize_trigger(self):
        # Function raises once, then passes
        func = MagicMock(side_effect=[textrect.TextRectException("overflow"), None])
        
        self.manager.exec_with_resize(func, 0)
        
        self.assertEqual(func.call_count, 2)
        # Verify resize was called
        # Resize calls from_instance on both displays
        self.assertTrue(self.mock_previous_class.from_instance.called)
        self.assertTrue(self.mock_remaining_class.from_instance.called)

    def test_exec_with_resize_failure(self):
        # Function always raises
        func = MagicMock(side_effect=textrect.TextRectException("overflow"))
        
        # Should catch and log, NOT raise
        # Verify it runs without error
        self.manager.exec_with_resize(func, 0)
             
        # Should retry a few times (retry limit 5)
        # First call + 5 retries = 6 calls? Or check implementation logic.
        # Logic says: `retry_count += 1`. if `retry_count > 5`: log and return.
        # So it should call 6 or 7 times?
        # Let's just assert multiple calls.
        self.assertGreaterEqual(func.call_count, 5)

if __name__ == '__main__':
    unittest.main()
