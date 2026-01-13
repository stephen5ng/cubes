import pytest
from game.descent_strategy import UnifiedDescentStrategy

class TestUnifiedDescentStrategy:
    
    def test_infinite_mode_events_only(self):
        """Test classic behavior: only moves on events."""
        # Setup: No time duration (infinite), 10px per event
        strategy = UnifiedDescentStrategy(game_duration_ms=None, event_descent_amount=10)
        
        # 1. No movement on time update
        pos, triggered = strategy.update(current_y=0, now_ms=1000, height=100)
        assert pos == 0
        assert not triggered
        
        # 2. Trigger event
        strategy.trigger_descent()
        pos, triggered = strategy.update(current_y=0, now_ms=2000, height=100)
        assert pos == 10
        assert triggered is True
        
        # 3. Subsequent update clears trigger
        pos, triggered = strategy.update(current_y=10, now_ms=3000, height=100)
        assert pos == 10
        assert triggered is False

    def test_timed_mode_time_only(self):
        """Test timed behavior: moves based on time, ignores events if amount is 0."""
        # Setup: 1000ms duration for 100px height (0.1px/ms), no event movement
        strategy = UnifiedDescentStrategy(game_duration_ms=1000, event_descent_amount=0)
        
        # 1. Update halfway through
        # Note: height is passed to update() to calculate rate dynamically or cached?
        # The previous TimeBased strategy took total_height in __init__.
        # Let's check the design. The new one might take it in update or init.
        # UNCOMMITTED_CHANGES says: Game.__init__ accepts game_duration_s.
        # Let's assume the new strategy calculates target_y based on time fraction of height.
        
        # Standardize on passing height to update() for flexibility, 
        # OR strategy needs total_height in __init__ if rate is constant.
        # TimeBasedDescentStrategy took total_height in __init__.
        # Unified probably should too? Or maybe just duration.
        # If height changes (dynamic resizing?), passing it to update is better.
        # But for now let's assume update(..., height) is the way.
        
        start_ms = 0
        strategy.reset(start_ms)
        
        # 500ms elapsed = 50% progress
        pos, triggered = strategy.update(current_y=0, now_ms=500, height=100)
        assert pos == 50
        assert triggered is False
        
        # 1000ms elapsed = 100% progress
        pos, triggered = strategy.update(current_y=50, now_ms=1000, height=100)
        assert pos == 100
        assert triggered is False

    def test_hybrid_mode(self):
        """Test both time and events contributing."""
        # Setup: 10s duration (slow fall), plus events
        # 10000ms, 100px height -> 0.01px/ms
        strategy = UnifiedDescentStrategy(game_duration_ms=10000, event_descent_amount=10)
        strategy.reset(0)
        
        # 1. Time passes (1000ms -> 10px)
        pos, _ = strategy.update(current_y=0, now_ms=1000, height=100)
        assert pos == 10
        
        # 2. Trigger event (+10px)
        strategy.trigger_descent()
        pos, triggered = strategy.update(current_y=10, now_ms=1000, height=100)
        # Should be time_pos (10) + event_offset (10) = 20?
        # Or does event change the base "time" tracking?
        # Implementation detail: Does force_position update the time anchor?
        # Let's assume events add to a separate offset or force position.
        
        # Logic: New Y = TimeBasedY + EventBasedY ? 
        # Or is it stateful?
        # If I drop 10px, does the time-based fall continue from there?
        # Usually yes.
        assert pos == 20
        assert triggered is True

    def test_reset(self):
        strategy = UnifiedDescentStrategy(game_duration_ms=1000, event_descent_amount=10)
        strategy.trigger_descent()
        strategy.update(0, 100, 100)
        
        strategy.reset(200)
        assert strategy.start_time_ms == 200
        # Internal state should be cleared
        pos, triggered = strategy.update(0, 200, 100)
        assert pos == 0
        assert not triggered
