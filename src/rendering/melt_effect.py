import pygame
import random
from typing import List, Dict, Optional, Any
import easing_functions

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
            # Calculate random duration based on previous physics
            # d = 0.5 * a * t^2  ->  t = sqrt(2*d/a)
            # a ~ 0.2, d ~ height
            # But let's just tune it to look good: 60-120 frames (1-2 seconds at 60fps)
            duration = random.uniform(60, 120)
            
            easing = easing_functions.ExponentialEaseIn(
                start=0, 
                end=self.height, 
                duration=duration
            )
            
            self.columns.append({
                'y': 0.0,
                'timer': 0.0,
                'delay': random.uniform(0, 20),
                'easing': easing,
                'finished': False
            })

    def update(self) -> None:
        """Update the physics of the melting columns."""
        for col in self.columns:
            if col['delay'] > 0:
                col['delay'] -= 1
            elif not col['finished']:
                col['timer'] += 1
                new_y = col['easing'](col['timer'])
                col['y'] = new_y
                
                # Check completion
                if new_y >= self.height:
                    col['finished'] = True

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
