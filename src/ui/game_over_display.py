import pygame
import pygame.freetype
from config.game_config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FONT,
    GOOD_GUESS_COLOR,
    BAD_GUESS_COLOR
)

class GameOverDisplay:
    """Display for game over state (Win/Loss)."""

    def __init__(self) -> None:
        # Use a large font size for the message
        # Size 32 fits "CONGRATS!" (9 chars) on 192px screen
        self.font = pygame.freetype.SysFont(FONT, 32)
        
    def draw(self, window: pygame.Surface, won: bool) -> None:
        """Render the game over message centered on the screen."""
        text = "CONGRATS!" if won else "SORRY"
        color = GOOD_GUESS_COLOR if won else BAD_GUESS_COLOR
        
        # Render text
        text_surface, rect = self.font.render(text, color)
        
        # Center position
        x = (SCREEN_WIDTH - rect.width) // 2
        y = (SCREEN_HEIGHT - rect.height) // 2
        
        window.blit(text_surface, (x, y))
