"""Tests for Letter descent behavior before refactoring.

These tests capture current behavior to ensure refactoring doesn't break it.
"""
import pytest
import pygame
import pygame.freetype
from unittest.mock import Mock
from game.letter import Letter
from rendering.metrics import RackMetrics
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
