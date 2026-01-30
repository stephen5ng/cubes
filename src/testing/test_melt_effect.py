import unittest
import pygame
from rendering.melt_effect import MeltEffect

class TestMeltEffect(unittest.TestCase):
    def setUp(self):
        # Create a small surface for testing
        self.width = 10
        self.height = 100 # sufficient height to allow acceleration to show
        self.surface = pygame.Surface((self.width, self.height))
        self.surface.fill((255, 0, 0))
        self.melt = MeltEffect(self.surface)

    def test_initialization(self):
        """Test that columns are initialized with proper interface properties."""
        self.assertEqual(len(self.melt.columns), self.width)
        for col in self.melt.columns:
            # These properties must exist in both implementations
            self.assertIn('y', col)
            self.assertIn('delay', col)
            
            # Initial state
            self.assertEqual(col['y'], 0.0)
            self.assertGreaterEqual(col['delay'], 0)

    def test_update_delay(self):
        """Test that columns wait for their delay before moving."""
        # Pick the first column
        col = self.melt.columns[0]
        
        # Force a specific delay via the common interface key
        col['delay'] = 5
        # Ensure y is 0 (should be from init)
        original_y = col['y']
        
        # Update once
        self.melt.update()
        
        # Should detect delay decremented
        self.assertEqual(col['delay'], 4)
        # Should not have moved
        self.assertEqual(col['y'], original_y)

    def test_update_movement_acceleration(self):
        """Test that columns move downwards and accelerate (delta increases).
        This test is agnostic to checking 'vel', 'acc', or 'easing' directly.
        """
        # Pick a column
        col = self.melt.columns[0]
        
        # Force delay to 0 so it starts moving immediately
        col['delay'] = 0
        
        y_positions = []
        # Capture positions over several frames
        # We need enough frames to detect acceleration, but not pass height (100)
        # With accel ~0.2 or EaseIn over 60-120 frames, 10 frames is safe.
        y_positions.append(col['y'])
        
        for _ in range(10):
            self.melt.update()
            y_positions.append(col['y'])
            
        # Verify downward movement (monotonic increase of y)
        for i in range(len(y_positions) - 1):
            self.assertGreater(y_positions[i+1], y_positions[i], 
                             f"Column did not move down at frame {i}: {y_positions}")
            
        # Verify acceleration (increase of delta_y)
        # delta_y_1 < delta_y_2 < ...
        deltas = [y_positions[i+1] - y_positions[i] for i in range(len(y_positions) - 1)]
        
        # We check that deltas are generally increasing. 
        # Note: ExponentialEaseIn start value at t=0 is slightly non-zero (2^-10 * change),
        # but our initial y is 0. This causes the first step (0 -> easing(1)) to be larger
        # than the second step (easing(1) -> easing(2)). 
        # So we skip the first delta for the acceleration check.
        valid_deltas = deltas[1:]
        accel_checks = [valid_deltas[i+1] > valid_deltas[i] for i in range(len(valid_deltas) - 1)]
        
        self.assertTrue(all(accel_checks), f"Movement did not accelerate: {deltas}")

    def test_draw(self):
        """Test that the effect draws correctly offset columns."""
        # Use a fresh melt with known state
        # Force column 5 to be at y=5
        col_idx = 5
        self.melt.columns[col_idx]['delay'] = 0
        
        # Note: We cannot just set 'y' directly and expect physics to work in 'update',
        # but 'draw' only reads 'y'. So setting 'y' is valid for testing draw.
        self.melt.columns[col_idx]['y'] = 5.0
        
        # Target surface
        target = pygame.Surface((self.width, self.height))
        target.fill((0, 0, 0)) # Black
        
        self.melt.draw(target)
        
        # Check logic:
        # Source at (5, 0) is Red.
        # Column 5 shifted down by 5.
        # So Target at (5, 5) should be Red.
        color_at_fall = target.get_at((5, 5))
        self.assertEqual(color_at_fall, (255, 0, 0, 255))
        
        # Above the fall should remain background (Black)
        # because the column moved away
        color_above = target.get_at((5, 4))
        self.assertEqual(color_above, (0, 0, 0, 255))

if __name__ == '__main__':
    unittest.main()
