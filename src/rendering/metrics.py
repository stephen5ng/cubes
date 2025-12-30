"""Metrics and layout calculations for game rendering."""

import pygame
import pygame.freetype
import sys
import os

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from core import tiles


# Constants from main game
SCREEN_WIDTH = 192
SCREEN_HEIGHT = 256
FONT = "Courier"


class RackMetrics:
    """Calculates layout metrics for the letter rack display."""
    
    LETTER_SIZE = 24
    LETTER_BORDER = 0
    BOTTOM_MARGIN = 1
    
    def __init__(self) -> None:
        self.font = pygame.freetype.SysFont(FONT, self.LETTER_SIZE)
        self.letter_width = self.font.get_rect("A").size[0] + self.LETTER_BORDER
        self.letter_height = self.font.get_rect("S").size[1] + self.LETTER_BORDER + self.BOTTOM_MARGIN
        self.x = SCREEN_WIDTH/2 - self.letter_width * tiles.MAX_LETTERS/2
        self.y = SCREEN_HEIGHT - self.letter_height

    def get_rect(self) -> pygame.Rect:
        """Get the bounding rectangle of the entire rack."""
        return pygame.Rect(
            self.x,
            self.y,
            self.letter_width * tiles.MAX_LETTERS,
            self.letter_height)

    def get_letter_rect(self, position: int, letter: str) -> pygame.Rect:
        """Get the rectangle for a specific letter at a position."""
        this_letter_width = self.font.get_rect(letter).width
        this_letter_margin = (self.letter_width - this_letter_width) / 2
        x = self.letter_width * position + this_letter_margin
        y = self.LETTER_BORDER/2 + self.BOTTOM_MARGIN
        return pygame.Rect(x, y, this_letter_width, self.letter_height - self.LETTER_BORDER)

    def get_largest_letter_rect(self, position: int) -> pygame.Rect:
        """Get the largest possible rectangle for a letter at a position."""
        x = self.letter_width * position + self.LETTER_BORDER/2
        y = self.LETTER_BORDER/2
        return pygame.Rect(x, y, self.letter_width - self.LETTER_BORDER,
                          self.letter_height - self.LETTER_BORDER)

    def get_size(self) -> tuple[int, int]:
        """Get the size of the rack."""
        return self.get_rect().size

    def get_select_rect(self, select_count: int, player: int) -> pygame.Rect:
        """Get the rectangle for selected letters based on player and count."""
        if player == 1:
            # For player 1, start from right side and expand left
            x = self.letter_width * (tiles.MAX_LETTERS - select_count)
            return pygame.Rect(x, 0, self.letter_width * select_count, self.letter_height)
        else:
            # For player 0, start from left side and expand right (original behavior)
            return pygame.Rect(0, 0, self.letter_width * select_count, self.letter_height)