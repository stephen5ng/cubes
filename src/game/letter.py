"""Falling letter animation and game entity."""

from enum import Enum
import easing_functions
import pygame
import pygame.freetype
from typing import Optional

from core import tiles
from config import game_config
from config.game_config import SCREEN_HEIGHT, LETTER_SOURCE_COLOR
from rendering.metrics import RackMetrics
from game.descent_strategy import DescentStrategy


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
        self, font: pygame.freetype.Font, initial_y: int, rack_metrics: RackMetrics, output_logger, letter_beeps: list,
        descent_strategy: Optional[DescentStrategy] = None) -> None:
        self.rack_metrics = rack_metrics
        self.game_area_offset_y = initial_y  # Offset from screen top to game area
        self.font = font
        self.letter_width, self.letter_height = rack_metrics.letter_width, rack_metrics.letter_height
        self.width = rack_metrics.letter_width
        self.height = SCREEN_HEIGHT - (rack_metrics.letter_height + initial_y)
        assert self.height > 0, f"Letter height must be positive, got {self.height} (screen={SCREEN_HEIGHT}, letter={rack_metrics.letter_height}, y={initial_y})"
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

        # Use strategy pattern for descent control
        if descent_strategy is None:
            descent_strategy = DescentStrategy(game_duration_ms=None, event_descent_amount=Letter.Y_INCREMENT)
        self.descent_strategy = descent_strategy

        self.start(0)
        self.draw(0)

    def _get_fall_percent(self, now_ms: int) -> float:
        """Calculate the current fall completion percentage (0.0 to 1.0)."""
        remaining_height = self.height - self.start_fall_y
        
        if remaining_height <= 0:
            return 1.0

        # Calculate duration dynamically based on current line position
        # self.height > 0 invariant enforced in __init__
        current_duration_ms = self.DROP_TIME_MS * remaining_height / self.height

        return (now_ms - self.start_fall_time_ms) / current_duration_ms

    def _compute_fall_y(self, now_ms: int) -> int:
        """Compute Y position based on current time/state."""
        fall_percent = self._get_fall_percent(now_ms)
        fall_easing = self.top_bottom_easing(fall_percent)
        # Ensure letter never appears above the red line
        return max(self.start_fall_y, int(self.current_fall_start_y + fall_easing * self.height))

    def start(self, now_ms: int) -> None:
        """Initialize letter state for a new game."""
        self.letter = ""
        self.letter_ix = 1
        self.start_fall_y = 0
        self.current_fall_start_y = 0
        self.column_move_direction = 1
        self.next_column_move_time_ms = now_ms + self.NEXT_COLUMN_MS
        self.start_fall_time_ms = now_ms
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.pos = [0, 0]
        self.last_beep_time_ms = now_ms

        # Reset the descent strategy for new game
        self.descent_strategy.reset(now_ms)

    def stop(self) -> None:
        """Stop the letter animation."""
        self.letter = ""

    def freeze_at_position(self, position: int) -> None:
        """Freeze letter at specific rack position for deterministic testing.

        Sets the letter to be locked at a specific column index, preventing
        horizontal movement. This is primarily used in integration tests to
        ensure deterministic letter placement.

        Args:
            position: Rack index (0 to MAX_LETTERS-1, typically 0-5)

        Raises:
            ValueError: If position is outside valid range

        Example:
            # In tests - freeze letter at column 0 for predictable placement
            game.letter.freeze_at_position(0)
            game.letter.letter = "A"
            await game.accept_letter(0)
        """
        if not (0 <= position < game_config.MAX_LETTERS):
            raise ValueError(
                f"Invalid position {position}: must be in range [0, {game_config.MAX_LETTERS})"
            )

        self.letter_ix = position
        self.locked_on = True
        # Set fraction_complete to 1.0 so letter_index() returns letter_ix directly
        self.fraction_complete = 1.0
        self.fraction_complete_eased = 1.0
        # Set to far future so column movement never triggers
        self.next_column_move_time_ms = float('inf')

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
            self.letter_beeps[letter_beeps_ix].play()
            self.last_beep_time_ms = now_ms

    def _update_column_movement(self, now_ms: int) -> list[str]:
        """Update horizontal column movement and return incidents."""
        incidents = []
        if now_ms > self.next_column_move_time_ms:
            incidents.append("letter_column_move")
            if not self.locked_on:
                self.letter_ix = self.letter_ix + self.column_move_direction
                if self.letter_ix < 0 or self.letter_ix >= game_config.MAX_LETTERS:
                    self.column_move_direction *= -1
                    self.letter_ix = self.letter_ix + self.column_move_direction*2

                self.next_column_move_time_ms = now_ms + self.NEXT_COLUMN_MS
                pygame.mixer.Sound.play(self.bounce_sound)

            self.output_logger.log_letter_position_change(self.pos[0], self.pos[1], now_ms)
        return incidents

    def _calculate_position(self, now_ms: int) -> None:
        """Calculate letter position based on current time and movement."""
        if self.letter == "!!!!!!":
            # Special case for the "nuke" letter: force it to align with the rack (column 0 start)
            # and disable horizontal oscillation
            self.pos[0] = self.rack_metrics.get_rect().x
            self.fraction_complete = 1.0
            self.fraction_complete_eased = 1.0
            return

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
        if self.letter == "!!!!!!":
            # Render each ! separately to ensure it is centered over each slot
            rack_rect = self.rack_metrics.get_rect()
            self.surface = pygame.Surface((rack_rect.width, self.letter_height), pygame.SRCALPHA)
            for i in range(tiles.MAX_LETTERS):
                # get_letter_rect returns a rect with x/y relative to the rack's (0,0)
                dest_rect = self.rack_metrics.get_letter_rect(i, "!")
                # Render to the surface at the calculated position
                self.font.render_to(self.surface, dest_rect, "!", LETTER_SOURCE_COLOR)
        else:
            self.surface = self.font.render(self.letter, LETTER_SOURCE_COLOR)[0]
        self._calculate_position(now_ms)
        self._update_locked_state()

    def update(self, window: pygame.Surface, now_ms: int) -> None:
        """Update and render the letter, returning incidents."""
        incidents = []

        self.start_fall_y = self.descent_strategy.update(now_ms, self.height)

        self.pos[1] = self._compute_fall_y(now_ms)

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

    def _apply_descent(self, new_y: int, now_ms: int) -> None:
        """Apply descent to a specific Y position.

        Args:
            new_y: The new start_fall_y position
            now_ms: Current timestamp
        """
        self.start_fall_y = new_y

        self.pos[1] = self.current_fall_start_y = self.start_fall_y
        self.start_fall_time_ms = now_ms

        # Synchronize strategy state if needed
        if hasattr(self.descent_strategy, 'force_position'):
            self.descent_strategy.force_position(new_y, now_ms, self.height)

    def new_fall(self, now_ms: int) -> None:
        """Start a new falling segment."""
        # Trigger descent in the strategy
        self.descent_strategy.trigger_descent()

        # Get current red line position and start new fall from there
        new_y = self.descent_strategy.update(now_ms, self.height)
        self._apply_descent(new_y, now_ms)
