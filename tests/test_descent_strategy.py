"""Tests for descent strategy implementations."""
import pytest
from src.game.descent_strategy import (
    DiscreteDescentStrategy,
    TimeBasedDescentStrategy
)


class TestDiscreteDescentStrategy:
    """Test DiscreteDescentStrategy behavior."""

    def test_no_descent_until_triggered(self):
        """Strategy should not descend until trigger_descent() is called."""
        strategy = DiscreteDescentStrategy(increment=16)
        strategy.reset(now_ms=0)

        # Multiple updates without trigger should not change position
        for i in range(10):
            new_y, should_trigger = strategy.update(current_y=0, now_ms=i * 100, height=240)
            assert new_y == 0
            assert should_trigger is False

    def test_descent_after_trigger(self):
        """Strategy should descend after trigger_descent() is called."""
        strategy = DiscreteDescentStrategy(increment=16)
        strategy.reset(now_ms=0)

        # Trigger descent
        strategy.trigger_descent()

        # Next update should trigger new fall
        new_y, should_trigger = strategy.update(current_y=0, now_ms=1000, height=240)
        assert new_y == 16
        assert should_trigger is True

    def test_multiple_triggers_accumulate(self):
        """Multiple triggers before update should not accumulate."""
        strategy = DiscreteDescentStrategy(increment=16)
        strategy.reset(now_ms=0)

        # Multiple triggers
        strategy.trigger_descent()
        strategy.trigger_descent()
        strategy.trigger_descent()

        # Only one descent should occur
        new_y, should_trigger = strategy.update(current_y=0, now_ms=1000, height=240)
        assert new_y == 16
        assert should_trigger is True

        # No more descents after first update
        new_y, should_trigger = strategy.update(current_y=16, now_ms=2000, height=240)
        assert new_y == 16
        assert should_trigger is False

    def test_caps_at_height(self):
        """Strategy should not exceed total height."""
        strategy = DiscreteDescentStrategy(increment=16)
        strategy.reset(now_ms=0)

        strategy.trigger_descent()
        new_y, should_trigger = strategy.update(current_y=235, now_ms=1000, height=240)
        assert new_y == 240  # Capped at height
        assert should_trigger is True

    def test_reset_clears_pending(self):
        """Reset should clear pending descent."""
        strategy = DiscreteDescentStrategy(increment=16)
        strategy.reset(now_ms=0)

        strategy.trigger_descent()
        strategy.reset(now_ms=1000)

        # No descent after reset
        new_y, should_trigger = strategy.update(current_y=0, now_ms=2000, height=240)
        assert new_y == 0
        assert should_trigger is False


class TestTimeBasedDescentStrategy:
    """Test TimeBasedDescentStrategy behavior."""

    def test_descent_over_time(self):
        """Strategy should descend continuously based on elapsed time."""
        # 10 second game, 240 pixel height -> 24 pixels/second = 0.024 pixels/ms
        strategy = TimeBasedDescentStrategy(game_duration_ms=10000, total_height=240)
        strategy.reset(now_ms=0)

        # At 0ms
        new_y, should_trigger = strategy.update(current_y=0, now_ms=0, height=240)
        assert new_y == 0
        assert should_trigger is False  # Time-based never triggers

        # At 5000ms (halfway) -> 120 pixels
        new_y, should_trigger = strategy.update(current_y=0, now_ms=5000, height=240)
        assert new_y == 120
        assert should_trigger is False  # Continuous position update, no trigger

        # At 10000ms (end) -> 240 pixels
        new_y, should_trigger = strategy.update(current_y=120, now_ms=10000, height=240)
        assert new_y == 240
        assert should_trigger is False  # Continuous position update, no trigger

    def test_continuous_position_updates(self):
        """Position should update continuously without triggering."""
        strategy = TimeBasedDescentStrategy(game_duration_ms=10000, total_height=240)
        strategy.reset(now_ms=0)

        # First call at t=0
        new_y, should_trigger = strategy.update(current_y=0, now_ms=0, height=240)
        assert should_trigger is False

        # Second call at t=1000 (position changed)
        new_y, should_trigger = strategy.update(current_y=0, now_ms=1000, height=240)
        assert new_y == 24  # 1000ms * (240/10000) = 24
        assert should_trigger is False  # Never triggers - continuous update only

        # Third call at same time (position update based on time, not current_y)
        new_y, should_trigger = strategy.update(current_y=24, now_ms=1000, height=240)
        assert new_y == 24  # Same time = same position
        assert should_trigger is False

    def test_caps_at_total_height(self):
        """Strategy should not exceed total height."""
        strategy = TimeBasedDescentStrategy(game_duration_ms=10000, total_height=240)
        strategy.reset(now_ms=0)

        # Way past game duration
        new_y, should_trigger = strategy.update(current_y=0, now_ms=20000, height=240)
        assert new_y == 240
        assert should_trigger is False  # Never triggers - continuous update only

    def test_reset_restarts_timer(self):
        """Reset should restart the timer."""
        strategy = TimeBasedDescentStrategy(game_duration_ms=10000, total_height=240)
        strategy.reset(now_ms=0)

        # Advance to halfway
        new_y, _ = strategy.update(current_y=0, now_ms=5000, height=240)
        assert new_y == 120

        # Reset at new time
        strategy.reset(now_ms=10000)

        # Should start from 0 again
        new_y, _ = strategy.update(current_y=0, now_ms=10000, height=240)
        assert new_y == 0

        # Halfway from reset point
        new_y, _ = strategy.update(current_y=0, now_ms=15000, height=240)
        assert new_y == 120


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
