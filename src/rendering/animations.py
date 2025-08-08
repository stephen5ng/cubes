"""Animation utilities and components for game rendering."""

import pygame
import easing_functions
import sys
import os

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

# Constants from main game
LETTER_SOURCE_COLOR = pygame.Color("Red")


def get_alpha(
    easing: easing_functions.easing.EasingBase, last_update: float, duration: float, now: int) -> int:
    """Calculate alpha value for fading animations.
    
    Args:
        easing: Easing function that controls the fade curve
        last_update: Timestamp when the fade started
        duration: Total duration of the fade in milliseconds
        now: Current timestamp
        
    Returns:
        Alpha value between 0-255, or 0 if fade is complete
    """
    remaining_ms = duration - (now - last_update)
    if 0 < remaining_ms < duration:
        return int(easing(remaining_ms / duration))
    return 0


class LetterSource:
    """Visual indicator showing where letters fall from."""
    
    ALPHA = 128
    ANIMATION_DURAION_MS = 200
    MIN_HEIGHT = 1
    MAX_HEIGHT = 20
    
    def __init__(self, letter, x: int, width: int, initial_y: int) -> None:
        self.x = x
        self.last_y = 0
        self.initial_y = initial_y
        self.height = LetterSource.MIN_HEIGHT
        self.width = width
        self.letter = letter
        self.easing = easing_functions.QuinticEaseInOut(start=1, end=LetterSource.MAX_HEIGHT, duration=1)
        self.last_update = 0
        self.draw()

    def draw(self) -> None:
        """Draw the letter source indicator."""
        self.surface = pygame.Surface([self.width, self.height], pygame.SRCALPHA)
        self.surface.set_alpha(LetterSource.ALPHA)
        self.surface.fill(LETTER_SOURCE_COLOR)

    def update(self, window: pygame.Surface, now_ms: int) -> list:
        """Updates the letter source animation and position.
        
        The letter source is a visual indicator showing where letters fall from.
        When a letter starts falling, the source expands to full height and then
        animates back down to minimum height.
        
        Args:
            window: Surface to draw on
            now_ms: Current timestamp in milliseconds
            
        Returns:
            List of any incidents that occurred during update
        """
        incidents = []
        if self.last_y != self.letter.start_fall_y:
            # Letter started falling from a new position
            self.last_update = now_ms
            self.height = LetterSource.MAX_HEIGHT
            self.last_y = self.letter.start_fall_y
            self.draw()
        elif self.height > LetterSource.MIN_HEIGHT:
            # Animate height back down
            self.height = max(LetterSource.MIN_HEIGHT, 
                              get_alpha(self.easing, 
                                    self.last_update, 
                                    LetterSource.ANIMATION_DURAION_MS, 
                                    now_ms))
            self.draw()

        # Position source above falling letter
        self.pos = [self.x, self.initial_y + self.letter.start_fall_y - self.height]
        window.blit(self.surface, self.pos)
        return incidents