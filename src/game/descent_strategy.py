"""Strategies for controlling how the fall source descends toward player."""

from abc import ABC, abstractmethod
from typing import Tuple


class DescentStrategy(ABC):
    """Strategy for controlling how the fall source descends toward player."""

    @abstractmethod
    def update(self, current_y: int, now_ms: int, height: int) -> Tuple[int, bool]:
        """
        Update the descent position.

        Args:
            current_y: Current start_fall_y position
            now_ms: Current timestamp
            height: Total fall height available

        Returns:
            Tuple of (new_y_position, should_trigger_new_fall)
        """
        pass

    @abstractmethod
    def reset(self, now_ms: int) -> None:
        """Reset strategy state for new game."""
        pass


class DiscreteDescentStrategy(DescentStrategy):
    """Original behavior: descend by fixed increment on events.

    This strategy maintains the classic game behavior where the fall source
    moves down in discrete steps only when triggered by game events (like
    completing a word or the letter hitting the rack).
    """

    def __init__(self, increment: int):
        """
        Args:
            increment: Distance to descend on each trigger (e.g., Y_INCREMENT)
        """
        self.increment = increment
        self.pending_descent = False

    def trigger_descent(self) -> None:
        """Called when word played/missed to trigger next descent."""
        self.pending_descent = True

    def update(self, current_y: int, now_ms: int, height: int) -> Tuple[int, bool]:
        """Apply pending descent if triggered."""
        if self.pending_descent:
            self.pending_descent = False
            new_y = min(current_y + self.increment, height)
            return (new_y, new_y > current_y)
        return (current_y, False)

    def reset(self, now_ms: int) -> None:
        """Clear pending descent."""
        self.pending_descent = False


class TimeBasedDescentStrategy(DescentStrategy):
    """Continuous descent based on elapsed time.

    This strategy creates a fixed-duration game mode by making the fall source
    descend at a constant rate regardless of player performance. Perfect for
    timed competitive modes (e.g., 3-minute games).
    """

    def __init__(self, game_duration_ms: int, total_height: int):
        """
        Args:
            game_duration_ms: Total game time (e.g., 180000 for 3 minutes)
            total_height: Total distance to descend
        """
        self.game_duration_ms = game_duration_ms
        self.total_height = total_height
        self.descent_rate = total_height / game_duration_ms  # pixels per ms
        self.start_time_ms = 0
        self.last_y = 0

    def update(self, current_y: int, now_ms: int, height: int) -> Tuple[int, bool]:
        """Calculate position based on elapsed time."""
        elapsed_ms = now_ms - self.start_time_ms
        target_y = min(self.total_height,
                      int(elapsed_ms * self.descent_rate))

        # Time-based strategy continuously updates position but doesn't trigger new falls
        # The red line descends, but the letter continues falling independently
        self.last_y = target_y

        return (target_y, False)

    def reset(self, now_ms: int) -> None:
        """Reset timer for new game."""
        self.start_time_ms = now_ms
        self.last_y = 0
