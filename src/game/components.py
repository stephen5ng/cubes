"""Game components for score and shield display."""

import math
import pygame
import pygame.freetype
import sys
import os

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
import app

# Constants from main game
SCREEN_WIDTH = 192
SCREEN_HEIGHT = 256
FONT = "Courier"
SCORE_COLOR = pygame.Color("White")
TICKS_PER_SECOND = 45

# Import color constants that we need
FADER_COLOR_P0 = pygame.Color("orange")
FADER_COLOR_P1 = pygame.Color("lightblue")
FADER_PLAYER_COLORS = [FADER_COLOR_P0, FADER_COLOR_P1]


class Score:
    """Displays and manages player score."""
    
    def __init__(self, the_app: app.App, player: int, rack_metrics) -> None:
        self.the_app = the_app
        self.player = player
        
        # Required dependency injection - no fallback!
        self.font = pygame.freetype.SysFont(FONT, rack_metrics.LETTER_SIZE)
        self.pos = [0, 0]
        self.x = SCREEN_WIDTH/3 * (player+1)
        self.midscreen = SCREEN_WIDTH/2
        self.start()
        self.draw()

    def get_size(self) -> tuple[int, int]:
        """Get the size of the score display."""
        return self.surface.get_size()

    def start(self) -> None:
        """Initialize/reset the score."""
        self.score = 0
        self.draw()

    def draw(self) -> None:
        """Render the score text."""
        self.surface = self.font.render(str(self.score), SCORE_COLOR)[0]
        self.pos[0] = int((self.midscreen if self.the_app.player_count == 1 else self.x) 
                          - self.surface.get_width()/2)

    def update_score(self, score: int) -> None:
        """Add points to the score."""
        self.score += score
        self.draw()

    def update(self, window: pygame.Surface) -> None:
        """Render the score to the window."""
        window.blit(self.surface, self.pos)


class Shield:
    """Flying text shield that shows scored words."""
    
    def __init__(self, base_pos: tuple[int, int], letters: str, score: int, player: int, now_ms: int) -> None:
        self.font = pygame.freetype.SysFont("Arial", int(2+math.log(1+score)*8))
        self.letters = letters
        self.base_pos = [base_pos[0], float(base_pos[1])]
        self.base_pos[1] -= self.font.get_rect("A").height
        self.pos = [self.base_pos[0], self.base_pos[1]]
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.score = score
        self.active = True
        self.player = player
        self.start_time_ms = now_ms
        self.initial_speed = -math.log(1+score)
        self.acceleration_rate = 1.05
        self.surface = self.font.render(self.letters, FADER_PLAYER_COLORS[self.player])[0]
        self.pos[0] = int(SCREEN_WIDTH/2 - self.surface.get_width()/2)

    def update(self, window: pygame.Surface, now_ms: int) -> None:
        """Update and render the shield animation."""
        if self.active:
            update_count = (now_ms - self.start_time_ms) / (1000.0/TICKS_PER_SECOND)

            # Calculate position by summing up all previous speed contributions
            # This is a geometric series: initial_speed * (1 - (1.05)^update_count) / (1 - 1.05)
            displacement = self.initial_speed * (1 - (self.acceleration_rate ** update_count)) / (1 - self.acceleration_rate)
            self.pos[1] = self.base_pos[1] + displacement
            window.blit(self.surface, self.pos)

            # Get the tightest rectangle around the content for collision detection.
            self.rect = self.surface.get_bounding_rect().move(self.pos[0], self.pos[1])

    def letter_collision(self) -> None:
        """Handle collision with falling letter."""
        self.active = False
        self.pos[1] = SCREEN_HEIGHT