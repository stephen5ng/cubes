import unittest
import pygame
from rendering.melt_effect import MeltEffect

class TestMeltEffect(unittest.TestCase):
    def setUp(self):
        # Create a small surface for testing
        self.width = 10
        self.height = 20
        self.surface = pygame.Surface((self.width, self.height))
        # Fill it with a known color (Red) to test drawing
        self.surface.fill((255, 0, 0))
        self.melt = MeltEffect(self.surface)

    def test_initialization(self):
        """Test that columns are initialized with correct random ranges."""
        self.assertEqual(len(self.melt.columns), self.width)
        for col in self.melt.columns:
            self.assertEqual(col['y'], 0.0)
            self.assertEqual(col['vel'], 0.0)
            self.assertTrue(0.1 <= col['acc'] <= 0.3, f"Acc {col['acc']} out of range")
            self.assertTrue(0 <= col['delay'] <= 20, f"Delay {col['delay']} out of range")

    def test_update_delay(self):
        """Test that columns wait for their delay before moving."""
        # Find a column and force delay
        col_idx = 0
        self.melt.columns[col_idx]['delay'] = 5
        self.melt.columns[col_idx]['acc'] = 0.2
        self.melt.columns[col_idx]['y'] = 0.0
        self.melt.columns[col_idx]['vel'] = 0.0
        
        self.melt.update()
        
        col = self.melt.columns[col_idx]
        self.assertEqual(col['delay'], 4)
        self.assertEqual(col['y'], 0.0)
        self.assertEqual(col['vel'], 0.0)

    def test_update_movement(self):
        """Test that columns move according to velocity and acceleration."""
        col_idx = 0
        self.melt.columns[col_idx]['delay'] = 0
        acc = 0.2
        self.melt.columns[col_idx]['acc'] = acc
        self.melt.columns[col_idx]['y'] = 0.0
        self.melt.columns[col_idx]['vel'] = 0.0
        
        # First update
        self.melt.update()
        col = self.melt.columns[col_idx]
        self.assertAlmostEqual(col['vel'], acc)
        self.assertAlmostEqual(col['y'], acc)
        
        # Second update
        self.melt.update()
        col = self.melt.columns[col_idx]
        # v = v + a = 0.2 + 0.2 = 0.4
        # y = y + v = 0.2 + 0.4 = 0.6
        self.assertAlmostEqual(col['vel'], acc * 2)
        self.assertAlmostEqual(col['y'], acc + (acc * 2))

    def test_draw(self):
        """Test that the effect draws correctly offset columns."""
        # Force column 5 to fall by 5 pixels
        col_idx = 5
        self.melt.columns[col_idx]['delay'] = 0
        self.melt.columns[col_idx]['y'] = 5.0
        
        # Target surface (initialized to Black)
        target = pygame.Surface((self.width, self.height))
        target.fill((0, 0, 0))
        
        self.melt.draw(target)
        
        # We expect the pixel at (5, 5) on target to be Red ((255, 0, 0))
        # because the source surface was Red at (5, 0) and it fell 5 pixels.
        color_at_fall = target.get_at((5, 5))
        self.assertEqual(color_at_fall, (255, 0, 0, 255))
        
        # The pixel at (5, 4) should still be Black, because the column moved down
        # and nothing was drawn there (assuming blit doesn't draw clear pixels from above y=0)
        # The source rect is (x, 0, 1, height).
        # We blit that rect to (x, 5).
        # So nothing touches y < 5.
        color_above = target.get_at((5, 4))
        self.assertEqual(color_above, (0, 0, 0, 255))

if __name__ == '__main__':
    unittest.main()
