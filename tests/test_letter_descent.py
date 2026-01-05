"""Tests for Letter descent behavior before refactoring.

These tests capture current behavior to ensure refactoring doesn't break it.
"""
import pytest
import pygame
import pygame.freetype
from unittest.mock import Mock
from game.letter import Letter
from game.descent_strategy import TimeBasedDescentStrategy
from rendering.metrics import RackMetrics
from rendering.animations import LetterSource, PositionTracker, LETTER_SOURCE_RED, LETTER_SOURCE_YELLOW
from config.game_config import SCREEN_HEIGHT


@pytest.fixture
def letter_setup():
    """Setup Letter instance for testing."""
    pygame.init()
    pygame.freetype.init()
    pygame.mixer.init()

    rack_metrics = RackMetrics()
    font = rack_metrics.font
    output_logger = Mock()
    letter_beeps = [pygame.mixer.Sound("sounds/bounce.wav")]

    letter = Letter(
        font=font,
        initial_y=0,
        rack_metrics=rack_metrics,
        output_logger=output_logger,
        letter_beeps=letter_beeps
    )

    yield letter
    pygame.quit()


class TestLetterDescentBehavior:
    """Test current descent behavior before refactoring."""

    def test_initial_state(self, letter_setup):
        """Letter starts at top (start_fall_y = 0)."""
        letter = letter_setup
        letter.start(now_ms=0)
        assert letter.start_fall_y == 0
        assert letter.current_fall_start_y == 0

    def test_new_fall_increments_by_y_increment(self, letter_setup):
        """Each new_fall() increments start_fall_y by Y_INCREMENT."""
        letter = letter_setup
        letter.start(now_ms=0)

        initial_y = letter.start_fall_y
        letter.new_fall(now_ms=1000)

        assert letter.start_fall_y == initial_y + Letter.Y_INCREMENT
        assert letter.current_fall_start_y == letter.start_fall_y

    def test_multiple_falls_accumulate(self, letter_setup):
        """Multiple falls accumulate increments."""
        letter = letter_setup
        letter.start(now_ms=0)

        for i in range(5):
            letter.new_fall(now_ms=i * 1000)

        expected_y = Letter.Y_INCREMENT * 5
        assert letter.start_fall_y == expected_y

    def test_y_increment_equals_screen_height_divided_by_rounds(self, letter_setup):
        """Y_INCREMENT is calculated as SCREEN_HEIGHT // ROUNDS."""
        letter = letter_setup
        expected_increment = SCREEN_HEIGHT // Letter.ROUNDS
        assert Letter.Y_INCREMENT == expected_increment

    def test_fall_duration_decreases_with_height(self, letter_setup):
        """Fall duration decreases as start_fall_y increases."""
        letter = letter_setup
        letter.start(now_ms=0)

        # First fall - full duration
        letter.new_fall(now_ms=0)
        first_duration = letter.fall_duration_ms

        # Later fall - shorter duration
        for _ in range(5):
            letter.new_fall(now_ms=1000)
        later_duration = letter.fall_duration_ms

        assert later_duration < first_duration

        # Duration should be proportional to remaining height
        remaining_ratio = (letter.height - letter.start_fall_y) / letter.height
        expected_duration = Letter.DROP_TIME_MS * remaining_ratio
        assert abs(letter.fall_duration_ms - expected_duration) < 1

    def test_shield_collision_bounces_to_midpoint(self, letter_setup):
        """Shield collision sets position to midpoint between start and current."""
        letter = letter_setup
        letter.start(now_ms=0)
        letter.new_fall(now_ms=0)

        # Simulate fall partway
        letter.pos[1] = 100
        initial_start = letter.start_fall_y

        letter.shield_collision(now_ms=1000)

        # Should be at midpoint
        expected_midpoint = int(initial_start + (100 - initial_start) / 2)
        assert letter.pos[1] == expected_midpoint
        assert letter.current_fall_start_y == expected_midpoint

    def test_max_rounds_reaches_bottom(self, letter_setup):
        """After ROUNDS falls, should reach approximately screen bottom."""
        letter = letter_setup
        letter.start(now_ms=0)

        for i in range(Letter.ROUNDS):
            letter.new_fall(now_ms=i * 1000)

        # Should be at or past the height
        assert letter.start_fall_y >= letter.height - Letter.Y_INCREMENT


class TestLetterSourceIntegration:
    """Test that LetterSource correctly tracks start_fall_y."""

    def test_letter_source_tracks_start_fall_y(self, letter_setup):
        """LetterSource should detect when start_fall_y changes."""
        from rendering.animations import LetterSource

        letter = letter_setup
        letter.start(now_ms=0)

        # Create LetterSource
        letter_source = LetterSource(
            letter=letter,
            x=0,
            width=32,
            initial_y=0,
            descent_mode="discrete"
        )

        assert letter_source.last_y == 0

        # Trigger new fall
        start_y_before = letter.start_fall_y
        letter.new_fall(now_ms=1000)
        distance_moved = letter.start_fall_y - start_y_before

        # LetterSource should detect change on update
        window = pygame.Surface((100, 100))
        letter_source.update(window, now_ms=1000)

        assert letter_source.last_y == letter.start_fall_y
        # Height uses inclusive range: distance + 1 (clamped to MAX_HEIGHT)
        expected_height = min(distance_moved + 1, letter_source.MAX_HEIGHT)
        assert letter_source.height == expected_height


class TestLetterDescentEdgeCases:
    """Test edge cases in descent behavior."""

    def test_start_fall_y_never_exceeds_height(self, letter_setup):
        """start_fall_y should not exceed total height."""
        letter = letter_setup
        letter.start(now_ms=0)

        # Try many falls (more than ROUNDS)
        for i in range(Letter.ROUNDS + 10):
            letter.new_fall(now_ms=i * 1000)
            assert letter.start_fall_y <= letter.height

    def test_fall_duration_never_negative(self, letter_setup):
        """Fall duration should never be negative."""
        letter = letter_setup
        letter.start(now_ms=0)

        for i in range(Letter.ROUNDS + 5):
            letter.new_fall(now_ms=i * 1000)
            assert letter.fall_duration_ms >= 0

    def test_reset_via_start_clears_descent(self, letter_setup):
        """Calling start() should reset all descent state."""
        letter = letter_setup
        letter.start(now_ms=0)

        # Do some falls
        for i in range(5):
            letter.new_fall(now_ms=i * 1000)

        assert letter.start_fall_y > 0

        # Reset
        letter.start(now_ms=10000)

        assert letter.start_fall_y == 0
        assert letter.current_fall_start_y == 0
        assert letter.pos[1] == 0


class TestLetterDescentConstants:
    """Verify descent-related constants."""

    def test_rounds_is_15(self):
        """ROUNDS should be 15 (documented behavior)."""
        assert Letter.ROUNDS == 15

    def test_y_increment_calculation(self):
        """Y_INCREMENT should be SCREEN_HEIGHT // ROUNDS."""
        expected = SCREEN_HEIGHT // Letter.ROUNDS
        assert Letter.Y_INCREMENT == expected

    def test_drop_time_is_15_seconds(self):
        """DROP_TIME_MS should be 15000 (15 seconds)."""
        assert Letter.DROP_TIME_MS == 15000


class TestPositionTracker:
    """Test PositionTracker for visual indicators like yellow line."""

    def test_position_tracker_initialization(self):
        """PositionTracker should initialize with zero position."""
        strategy = TimeBasedDescentStrategy(game_duration_ms=10000, total_height=240)
        tracker = PositionTracker(strategy)
        
        assert tracker.start_fall_y == 0
        assert tracker.descent_strategy == strategy

    def test_position_tracker_update(self):
        """PositionTracker should update position based on strategy."""
        strategy = TimeBasedDescentStrategy(game_duration_ms=10000, total_height=240)
        tracker = PositionTracker(strategy)
        tracker.reset(now_ms=0)
        
        # After 5 seconds (half duration), should be at half height
        tracker.update(now_ms=5000, height=240)
        assert tracker.start_fall_y == 120  # Half of 240

    def test_position_tracker_reset(self):
        """PositionTracker should reset position on reset."""
        strategy = TimeBasedDescentStrategy(game_duration_ms=10000, total_height=240)
        tracker = PositionTracker(strategy)
        tracker.reset(now_ms=0)
        
        # Advance position
        tracker.update(now_ms=5000, height=240)
        assert tracker.start_fall_y == 120
        
        # Reset should go back to 0
        tracker.reset(now_ms=5000)
        assert tracker.start_fall_y == 0


class TestLetterSourceColor:
    """Test LetterSource color parameter."""

    def test_letter_source_default_color(self, letter_setup):
        """LetterSource should default to red color."""
        letter = letter_setup
        letter.start(now_ms=0)
        
        letter_source = LetterSource(
            letter=letter,
            x=0,
            width=32,
            initial_y=0,
            descent_mode="discrete"
        )
        
        assert letter_source.color == LETTER_SOURCE_RED

    def test_letter_source_custom_color(self, letter_setup):
        """LetterSource should accept custom color."""
        letter = letter_setup
        letter.start(now_ms=0)
        
        letter_source = LetterSource(
            letter=letter,
            x=0,
            width=32,
            initial_y=0,
            descent_mode="discrete",
            color=LETTER_SOURCE_YELLOW
        )
        
        assert letter_source.color == LETTER_SOURCE_YELLOW

    def test_letter_source_draws_with_custom_color(self, letter_setup):
        """LetterSource surface should use custom color."""
        letter = letter_setup
        letter.start(now_ms=0)
        
        yellow_source = LetterSource(
            letter=letter,
            x=0,
            width=32,
            initial_y=0,
            descent_mode="discrete",
            color=LETTER_SOURCE_YELLOW
        )
        
        # The surface should be filled with yellow color
        # We can't directly check the fill color, but we can verify it was created
        assert yellow_source.surface is not None
        assert yellow_source.color == LETTER_SOURCE_YELLOW


class TestYellowLineIntegration:
    """Test yellow line with PositionTracker."""

    def test_yellow_line_descends_slower(self):
        """Yellow line should descend at half the speed of red line."""
        # Red line: 10 second duration, 240 height
        red_strategy = TimeBasedDescentStrategy(game_duration_ms=10000, total_height=240)
        
        # Yellow line: 20 second duration (twice as long), same height
        yellow_strategy = TimeBasedDescentStrategy(game_duration_ms=20000, total_height=240)
        yellow_tracker = PositionTracker(yellow_strategy)
        
        red_strategy.reset(now_ms=0)
        yellow_tracker.reset(now_ms=0)
        
        # After 5 seconds
        red_y, _ = red_strategy.update(0, now_ms=5000, height=240)
        yellow_tracker.update(now_ms=5000, height=240)
        
        # Red should be at 50% (120 pixels)
        assert red_y == 120
        # Yellow should be at 25% (60 pixels) - half the speed
        assert yellow_tracker.start_fall_y == 60
        
        # After 10 seconds
        red_y, _ = red_strategy.update(red_y, now_ms=10000, height=240)
        yellow_tracker.update(now_ms=10000, height=240)
        
        # Red should be at 100% (240 pixels)
        assert red_y == 240
        # Yellow should be at 50% (120 pixels)
        assert yellow_tracker.start_fall_y == 120

    def test_yellow_line_with_letter_source(self):
        """Yellow line should work with LetterSource."""
        yellow_strategy = TimeBasedDescentStrategy(game_duration_ms=20000, total_height=240)
        yellow_tracker = PositionTracker(yellow_strategy)
        yellow_tracker.reset(now_ms=0)
        
        yellow_source = LetterSource(
            letter=yellow_tracker,
            x=0,
            width=32,
            initial_y=0,
            descent_mode="timed",
            color=LETTER_SOURCE_YELLOW
        )
        
        # Initial state
        assert yellow_source.color == LETTER_SOURCE_YELLOW
        assert yellow_source.last_y == 0
        
        # Update tracker position
        yellow_tracker.update(now_ms=5000, height=240)
        assert yellow_tracker.start_fall_y == 60
        
        # LetterSource should track the position
        window = pygame.Surface((100, 100))
        yellow_source.update(window, now_ms=5000)
        assert yellow_source.last_y == 60
