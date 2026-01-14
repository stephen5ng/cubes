from typing import Optional, Tuple

class UnifiedDescentStrategy:
    """Consolidated descent strategy handling both time and event-based descent."""

    def __init__(self, game_duration_ms: Optional[int], event_descent_amount: int):
        self.game_duration_ms = game_duration_ms
        self.event_descent_amount = event_descent_amount
        self.start_time_ms = 0
        self.event_offset = 0
        self.pending_descent = False

    def reset(self, now_ms: int) -> None:
        """Reset strategy state for new game."""
        self.start_time_ms = now_ms
        self.event_offset = 0
        self.pending_descent = False

    def trigger_descent(self) -> None:
        """Trigger an event-based descent (e.g. word formed)."""
        self.pending_descent = True

    def update(self, now_ms: int, height: int) -> int:
        """Calculates the new Y position based on time and events."""
        if self.pending_descent:
            self.event_offset += self.event_descent_amount
            self.pending_descent = False

        rate = 0.0
        if self.game_duration_ms:
            rate = height / self.game_duration_ms

        elapsed = now_ms - self.start_time_ms
        time_drop = int(elapsed * rate)

        target_y = time_drop + self.event_offset
        return min(target_y, height)

    def force_position(self, new_y: int, now_ms: int, height: int) -> None:
        """Force the strategy to adopt a new position (e.g. physics adjustment).
           This recalculates the event_offset so that update() yields new_y.
        """
        rate = 0.0
        if self.game_duration_ms:
            rate = height / self.game_duration_ms
        elapsed = now_ms - self.start_time_ms
        time_drop = int(elapsed * rate)
        self.event_offset = new_y - time_drop
