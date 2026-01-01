"""Tests for descent strategy implementations."""
import pytest
from src.game.descent_strategy import (
    DiscreteDescentStrategy,
    TimeBasedDescentStrategy,
    HybridDescentStrategy
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


class TestHybridDescentStrategy:
    """Test HybridDescentStrategy behavior."""

    def test_time_based_descent_alone(self):
        """Without triggers, should behave like TimeBasedDescentStrategy."""
        strategy = HybridDescentStrategy(
            game_duration_ms=10000,
            total_height=240,
            event_increment=16
        )
        strategy.reset(now_ms=0)

        # At 5000ms -> 120 pixels
        new_y, should_trigger = strategy.update(current_y=0, now_ms=5000, height=240)
        assert new_y == 120
        assert should_trigger is True

    def test_event_based_descent_alone(self):
        """At game start, events should add to time-based descent."""
        strategy = HybridDescentStrategy(
            game_duration_ms=10000,
            total_height=240,
            event_increment=16
        )
        strategy.reset(now_ms=0)

        # Trigger event immediately
        strategy.trigger_descent()

        # At t=0, time-based is 0, event adds 16
        new_y, should_trigger = strategy.update(current_y=0, now_ms=0, height=240)
        assert new_y == 16
        assert should_trigger is True

    def test_combined_descent(self):
        """Events should add to time-based descent."""
        strategy = HybridDescentStrategy(
            game_duration_ms=10000,
            total_height=240,
            event_increment=16
        )
        strategy.reset(now_ms=0)

        # At 5000ms, time-based is 120
        new_y, _ = strategy.update(current_y=0, now_ms=5000, height=240)
        assert new_y == 120

        # Trigger event
        strategy.trigger_descent()

        # Should add 16 to time-based (120)
        new_y, should_trigger = strategy.update(current_y=120, now_ms=5000, height=240)
        assert new_y == 136  # 120 + 16
        assert should_trigger is True

    def test_event_descent_consumed(self):
        """Event descent should be consumed after applied."""
        strategy = HybridDescentStrategy(
            game_duration_ms=10000,
            total_height=240,
            event_increment=16
        )
        strategy.reset(now_ms=0)

        # Trigger event
        strategy.trigger_descent()

        # Apply event descent
        new_y, _ = strategy.update(current_y=0, now_ms=0, height=240)
        assert new_y == 16

        # Event should be consumed
        new_y, should_trigger = strategy.update(current_y=16, now_ms=0, height=240)
        assert new_y == 16
        assert should_trigger is False

    def test_multiple_events_accumulate(self):
        """Multiple events should accumulate."""
        strategy = HybridDescentStrategy(
            game_duration_ms=10000,
            total_height=240,
            event_increment=16
        )
        strategy.reset(now_ms=0)

        # Trigger multiple events
        strategy.trigger_descent()
        strategy.trigger_descent()
        strategy.trigger_descent()

        # All should be applied
        new_y, should_trigger = strategy.update(current_y=0, now_ms=0, height=240)
        assert new_y == 48  # 16 * 3
        assert should_trigger is True

    def test_caps_at_height(self):
        """Combined descent should not exceed height."""
        strategy = HybridDescentStrategy(
            game_duration_ms=10000,
            total_height=240,
            event_increment=16
        )
        strategy.reset(now_ms=0)

        # Time-based at end (240)
        # Plus events (48)
        strategy.trigger_descent()
        strategy.trigger_descent()
        strategy.trigger_descent()

        new_y, should_trigger = strategy.update(current_y=0, now_ms=10000, height=240)
        assert new_y == 240  # Capped
        assert should_trigger is True

    def test_reset_clears_both(self):
        """Reset should clear both time and event state."""
        strategy = HybridDescentStrategy(
            game_duration_ms=10000,
            total_height=240,
            event_increment=16
        )
        strategy.reset(now_ms=0)

        # Advance time and trigger events
        strategy.trigger_descent()
        strategy.update(current_y=0, now_ms=5000, height=240)

        # Reset
        strategy.reset(now_ms=10000)

        # Should start fresh
        new_y, should_trigger = strategy.update(current_y=0, now_ms=10000, height=240)
        assert new_y == 0
        assert should_trigger is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
