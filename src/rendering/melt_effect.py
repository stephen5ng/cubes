import pygame
import random
from typing import List, Dict, Optional

class MeltEffect:
    """Handles the screen melt animation effect."""

    def __init__(self, source_surface: pygame.Surface):
        self.source_surface = source_surface.copy()
        self.width, self.height = self.source_surface.get_size()
        self.columns: List[Dict[str, float]] = []
        self._init_columns()

    def _init_columns(self) -> None:
        """Initialize the physics state for each column."""
        self.columns = []
        for _ in range(self.width):
            self.columns.append({
                'y': 0.0,
                'vel': 0.0,
                'acc': random.uniform(0.1, 0.3),  # Gravity variance
                'delay': random.uniform(0, 20)    # Start delay frames
            })

    def update(self) -> None:
        """Update the physics of the melting columns."""
        for col in self.columns:
            if col['delay'] > 0:
                col['delay'] -= 1
            else:
                col['vel'] += col['acc']
                col['y'] += col['vel']

    def draw(self, target_surface: pygame.Surface) -> None:
        """Draw the melting effect onto the target surface.
        
        Args:
            target_surface: The surface to draw onto. Context is assumed to be cleared 
                          (or handled by caller) if transparency is involved, 
                          but here we blit opaque columns.
        """
        # We blit distinct columns.
        # Optimization: We could lock surfaces, but for this resolution/python, blit is likely fines.
        for x, col in enumerate(self.columns):
            dest_y = int(col['y'])
            if dest_y < self.height:
                # copy one column of pixels from source at (x, 0) to target at (x, dest_y)
                # target_surface.blit(self.source_surface, (x, dest_y), area=pygame.Rect(x, 0, 1, self.height))
                
                # Note: The original code used:
                # window.blit(self.melt_surface, (x, dest_y), area=pygame.Rect(x, 0, 1, height))
                # This copies the FULL column height, shifted down. 
                # This means the top of the column draws "transparency" or "nothing" if source had it?
                # Actually source is a screenshot.
                target_surface.blit(self.source_surface, (x, dest_y), area=pygame.Rect(x, 0, 1, self.height))

    def is_done(self) -> bool:
        """Check if all columns have fallen off screen."""
        # Optional helper, not strictly required by current code but good for future.
        return all(col['y'] >= self.height for col in self.columns)
