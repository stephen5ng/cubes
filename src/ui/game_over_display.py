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
    """Display for game over or pre-game messages."""

    def __init__(self) -> None:
        # Use a large font size for the message
        # Size 32 fits "CONGRATS!" (9 chars) on 192px screen
        self.font = pygame.freetype.SysFont(FONT, 32)
        
    def draw_text(self, window: pygame.Surface, text: str, color: pygame.Color, alpha: int = 255) -> None:
        """Render multi-line text centered on the screen."""
        lines = text.split('\n')
        line_surfaces = []
        total_height = 0

        for line in lines:
            text_surface, rect = self.font.render(line, color)
            if alpha < 255:
                # Create a copy with alpha
                text_surface = text_surface.copy()
                text_surface.set_alpha(alpha)
            line_surfaces.append((text_surface, rect))
            total_height += rect.height
            
        # Add some spacing between lines
        line_spacing = 8
        total_height += line_spacing * (len(lines) - 1)
        
        # Start Y position to center the block of text
        current_y = (SCREEN_HEIGHT - total_height) // 2
        
        for text_surface, rect in line_surfaces:
            x = (SCREEN_WIDTH - rect.width) // 2
            window.blit(text_surface, (x, current_y))
            current_y += rect.height + line_spacing

    def draw(self, window: pygame.Surface, won: bool, now_ms: int = 0) -> None:
        """Render the game over message centered on the screen."""
        text = "CONGRATS!" if won else "SORRY"
        color = GOOD_GUESS_COLOR if won else BAD_GUESS_COLOR

        # Simple blink for winning: 400ms on, 400ms off
        if won and now_ms > 0:
            BLINK_INTERVAL_MS = 500
            if (now_ms // BLINK_INTERVAL_MS) % 2 == 1:
                return  # Skip drawing during the "off" phase

        self.draw_text(window, text, color)
