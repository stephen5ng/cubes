"""Falling letter animation and game entity."""

from enum import Enum
import easing_functions
import pygame
import pygame.freetype

from core import tiles
from src.config.display_constants import SCREEN_HEIGHT, LETTER_SOURCE_COLOR
from src.rendering.metrics import RackMetrics


class GuessType(Enum):
    """Types of guess validation results."""
    BAD = 0
    OLD = 1
    GOOD = 2


class Letter:
    """Handles falling letter animation with column movement and physics."""

    DROP_TIME_MS = 15000
    NEXT_COLUMN_MS = 1000
    ANTIALIAS = 1
    ROUNDS = 15
    Y_INCREMENT = SCREEN_HEIGHT // ROUNDS
    COLUMN_SHIFT_INTERVAL_MS = 10000

    def __init__(
        self, font: pygame.freetype.Font, initial_y: int, rack_metrics: RackMetrics, output_logger, letter_beeps: list) -> None:
        self.rack_metrics = rack_metrics
        self.game_area_offset_y = initial_y  # Offset from screen top to game area
        self.font = font
        self.letter_width, self.letter_height = rack_metrics.letter_width, rack_metrics.letter_height
        self.width = rack_metrics.letter_width
        self.height = SCREEN_HEIGHT - (rack_metrics.letter_height + initial_y)
        self.fraction_complete = 0.0
        self.locked_on = False
        self.start_x = self.rack_metrics.get_rect().x
        self.bounce_sound = pygame.mixer.Sound("sounds/bounce.wav")
        self.bounce_sound.set_volume(0.1)
        self.next_letter_easing = easing_functions.ExponentialEaseOut(start=0, end=1, duration=1)
        self.left_right_easing = easing_functions.ExponentialEaseIn(start=1000, end=10000, duration=1)
        self.top_bottom_easing = easing_functions.CubicEaseIn(start=0, end=1, duration=1)
        self.output_logger = output_logger
        self.letter_beeps = letter_beeps

        self.start(0)
        self.draw(0)

    def start(self, now_ms: int) -> None:
        """Initialize letter state for a new game."""
        self.letter = ""
        self.letter_ix = 1
        self.start_fall_y = 0
        self.current_fall_start_y = 0
        self.column_move_direction = 1
        self.next_column_move_time_ms = now_ms + self.NEXT_COLUMN_MS
        self.fall_duration_ms = self.DROP_TIME_MS
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.pos = [0, 0]
        self.start_fall_time_ms = now_ms
        self.last_beep_time_ms = now_ms

    def stop(self) -> None:
        """Stop the letter animation."""
        self.letter = ""

    def letter_index(self) -> int:
        """Get the current letter index in the rack."""
        if self.fraction_complete_eased >= 0.5:
            return self.letter_ix
        return self.letter_ix - self.column_move_direction

    def get_screen_bottom_y(self) -> int:
        """Get the bottom Y coordinate of the letter on screen."""
        return self.game_area_offset_y + self.pos[1] + self.letter_height

    def _update_beeping(self, now_ms: int) -> None:
        """Update beeping sound based on letter position."""
        distance_from_top = self.pos[1] / SCREEN_HEIGHT
        distance_from_bottom = 1 - distance_from_top
        if now_ms > self.last_beep_time_ms + (distance_from_bottom*distance_from_bottom)*7000:
            letter_beeps_ix = min(len(self.letter_beeps)-1, int(10*distance_from_top))
            pygame.mixer.Sound.play(self.letter_beeps[letter_beeps_ix])
            self.last_beep_time_ms = now_ms

    def _update_column_movement(self, now_ms: int) -> list[str]:
        """Update horizontal column movement and return incidents."""
        incidents = []
        if now_ms > self.next_column_move_time_ms:
            incidents.append("letter_column_move")
            if not self.locked_on:
                self.letter_ix = self.letter_ix + self.column_move_direction
                if self.letter_ix < 0 or self.letter_ix >= tiles.MAX_LETTERS:
                    self.column_move_direction *= -1
                    self.letter_ix = self.letter_ix + self.column_move_direction*2

                self.next_column_move_time_ms = now_ms + self.NEXT_COLUMN_MS
                pygame.mixer.Sound.play(self.bounce_sound)

            self.output_logger.log_letter_position_change(self.pos[0], self.pos[1], now_ms)
        return incidents

    def _calculate_position(self, now_ms: int) -> None:
        """Calculate letter position based on current time and movement."""
        remaining_ms = min(max(0, self.next_column_move_time_ms - now_ms), self.NEXT_COLUMN_MS)
        self.fraction_complete = 1.0 - remaining_ms/self.NEXT_COLUMN_MS
        self.fraction_complete_eased = self.next_letter_easing(self.fraction_complete)
        boost_x = 0 if self.locked_on else int(self.column_move_direction*(self.width*(self.fraction_complete_eased - 1)))
        self.pos[0] = self.rack_metrics.get_rect().x + self.rack_metrics.get_letter_rect(self.letter_ix, self.letter).x + boost_x

    def _update_locked_state(self) -> None:
        """Update whether the letter is locked onto the rack."""
        self.locked_on = (self.fraction_complete_eased >= 1) and (self.get_screen_bottom_y() + Letter.Y_INCREMENT*2 > self.height)

    def draw(self, now_ms) -> None:
        """Render the letter surface."""
        self.surface = self.font.render(self.letter, LETTER_SOURCE_COLOR)[0]
        self._calculate_position(now_ms)
        self._update_locked_state()

    def update(self, window: pygame.Surface, now_ms: int) -> None:
        """Update and render the letter, returning incidents."""
        incidents = []
        fall_percent = (now_ms - self.start_fall_time_ms)/self.fall_duration_ms
        fall_easing = self.top_bottom_easing(fall_percent)
        self.pos[1] = int(self.current_fall_start_y + fall_easing * self.height)

        self._update_beeping(now_ms)
        self.draw(now_ms)

        screen_pos = self.pos.copy()
        screen_pos[1] += self.game_area_offset_y
        window.blit(self.surface, screen_pos)

        incidents.extend(self._update_column_movement(now_ms))
        return incidents

    def shield_collision(self, now_ms: int) -> None:
        """Handle collision with shield - bounce back the letter."""
        # Calculate midpoint between start and current position
        midpoint = int(self.start_fall_y + (self.pos[1] - self.start_fall_y) / 2)
        self.pos[1] = midpoint
        self.current_fall_start_y = midpoint
        self.start_fall_time_ms = now_ms

    def change_letter(self, new_letter: str, now_ms: int) -> None:
        """Change the displayed letter."""
        self.letter = new_letter
        self.draw(now_ms)

    def new_fall(self, now_ms: int) -> None:
        """Start a new falling segment."""
        # Cap at height to prevent overflow
        self.start_fall_y = min(self.start_fall_y + Letter.Y_INCREMENT, self.height)

        # Ensure duration is never negative
        remaining_height = max(0, self.height - self.start_fall_y)
        self.fall_duration_ms = self.DROP_TIME_MS * remaining_height / self.height

        self.pos[1] = self.current_fall_start_y = self.start_fall_y
        self.start_fall_time_ms = now_ms
