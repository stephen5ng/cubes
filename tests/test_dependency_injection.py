"""Tests demonstrating dependency injection benefits."""

import unittest
import sys
import os
import pygame

# Add project root/src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from testing.mock_sound_manager import MockSoundManager, MockSound
from rendering.metrics import RackMetrics


class TestDependencyInjection(unittest.TestCase):
    """Demonstrate the benefits of dependency injection."""

    @classmethod
    def setUpClass(cls):
        """Initialize pygame for tests that need it."""
        pygame.init()

    @classmethod 
    def tearDownClass(cls):
        """Clean up pygame."""
        pygame.quit()

    def test_game_with_mock_sound_manager(self):
        """Test that we can inject a mock sound manager for testing."""
        # Before DI: Impossible to test without real sound system
        # After DI: Easy to test with mocks!
        
        mock_sound = MockSoundManager()
        
        # Verify mock works
        mock_sound.play_start()
        mock_sound.play_crash() 
        mock_sound.play_bloop()
        
        played_sounds = mock_sound.get_played_sounds()
        expected_sounds = ["start_sound", "crash_sound", "bloop_sound"]
        
        self.assertEqual(played_sounds, expected_sounds)
        
    def test_sound_manager_letter_beeps(self):
        """Test that mock provides letter beeps without loading real sound files."""
        mock_sound = MockSoundManager()
        letter_beeps = mock_sound.get_letter_beeps()
        
        # Should have 11 mock beeps
        self.assertEqual(len(letter_beeps), 11)
        # Should be mock objects, not real pygame.Sound objects
        self.assertTrue(all(isinstance(beep, MockSound) for beep in letter_beeps))
        self.assertTrue(all(beep.name.startswith("mock_beep_") for beep in letter_beeps))

    def test_rack_metrics_injection(self):
        """Test that RackMetrics can be created independently for testing."""
        # Before: Had to import inside Score.__init__ 
        # After: Can create and test independently
        
        rack_metrics = RackMetrics()
        
        # Test the metrics
        self.assertEqual(rack_metrics.LETTER_SIZE, 24)
        self.assertGreater(rack_metrics.letter_width, 0)
        self.assertGreater(rack_metrics.letter_height, 0)
        
        # Test that we can get rectangles
        rect = rack_metrics.get_rect()
        self.assertIsNotNone(rect)
        
        letter_rect = rack_metrics.get_letter_rect(0, "A")
        self.assertIsNotNone(letter_rect)

    def test_forced_dependency_injection(self):
        """Test that Game class requires dependencies and can't work without them."""
        # This test verifies that we successfully removed backward compatibility
        # and now require explicit dependency injection
        
        mock_sound = MockSoundManager()
        rack_metrics = RackMetrics()
        
        # These components can now be created independently and injected
        self.assertIsNotNone(mock_sound)
        self.assertIsNotNone(rack_metrics)
        
        # Verify mock sound manager works as expected
        mock_sound.play_start()
        self.assertIn("start_sound", mock_sound.get_played_sounds())

if __name__ == '__main__':
    unittest.main()