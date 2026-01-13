"""Time provider abstraction for testability."""
from abc import ABC, abstractmethod
import pygame


class TimeProvider(ABC):
    """Abstract time provider for game timing."""

    @abstractmethod
    def get_ticks(self) -> int:
        """Get current time in milliseconds.

        Returns:
            Milliseconds since initialization
        """
        pass

    @abstractmethod
    def get_seconds(self) -> float:
        """Get current time in seconds.

        Returns:
            Seconds since initialization
        """
        pass


class SystemTimeProvider(TimeProvider):
    """Production time provider using pygame clock."""

    def get_ticks(self) -> int:
        """Get current time from pygame."""
        return pygame.time.get_ticks()

    def get_seconds(self) -> float:
        """Get current time in seconds."""
        return self.get_ticks() / 1000.0


class MockTimeProvider(TimeProvider):
    """Test time provider with controllable time."""

    def __init__(self, initial_ms: int = 0):
        """Initialize with specific time.

        Args:
            initial_ms: Starting time in milliseconds
        """
        self._current_ms = initial_ms

    def get_ticks(self) -> int:
        """Get mocked time."""
        return self._current_ms

    def get_seconds(self) -> float:
        """Get mocked time in seconds."""
        return self._current_ms / 1000.0

    def advance(self, ms: int) -> None:
        """Advance time by specified milliseconds.

        Args:
            ms: Milliseconds to advance
        """
        self._current_ms += ms

    def set_time(self, ms: int) -> None:
        """Set absolute time.

        Args:
            ms: Absolute time in milliseconds
        """
        self._current_ms = ms
