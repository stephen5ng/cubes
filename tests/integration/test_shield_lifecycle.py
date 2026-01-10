"""Shield Lifecycle Integration Tests

Tests shield creation, sizing, animation, and state transitions throughout
the shield's lifetime from word scoring to deactivation.

Run with:
    python3 -m pytest tests/integration/test_shield_lifecycle.py
    python3 -m pytest tests/integration/test_shield_lifecycle.py --visual
"""
import pytest
import math
import logging
from typing import List, Tuple

from game.components import Shield
from game.game_state import Game
from config import game_config
from config.game_config import (
    TICKS_PER_SECOND,
    SHIELD_ACCELERATION_RATE,
    SHIELD_INITIAL_SPEED_MULTIPLIER
)
from tests.fixtures.game_factory import (
    create_test_game,
    run_until_condition,
    advance_frames,
    async_test,
    FRAME_DURATION_MS,
    suppress_letter
)

logger = logging.getLogger(__name__)

# Test Constants - Shield Scores
RACK_TOP_Y = 100  # Typical rack position for shield creation
LOW_SCORE = 3
MEDIUM_SCORE = 15
HIGH_SCORE = 50
SHIELD_TEST_SCORE = 20  # Default score for animation tests

# Test Constants - Animation Tolerances
TRAJECTORY_TOLERANCE_PX = 10.0  # Tolerance for trajectory tests due to discrete frame timing

# Test Constants - Collision Setup
COLLISION_LETTER_OFFSET = 20  # Pixels above shield where letter is positioned for collision tests


def calculate_expected_font_size(score: int) -> int:
    """Calculate expected font size based on score formula: 2 + log(1+score) * 8"""
    return int(2 + math.log(1 + score) * 8)


def calculate_expected_displacement(score: int, now_ms: int) -> float:
    """Calculate expected shield vertical displacement after now_ms.

    Formula: initial_speed * (1 - acceleration_rate^update_count) / (1 - acceleration_rate)
    Where:
        initial_speed = -log(1+score) * SHIELD_INITIAL_SPEED_MULTIPLIER
        acceleration_rate = SHIELD_ACCELERATION_RATE
        update_count = (now_ms) / (1000.0 / TICKS_PER_SECOND)

    Args:
        score: Shield score value
        now_ms: Time elapsed in milliseconds

    Returns:
        Vertical displacement in pixels (negative means upward)
    """
    initial_speed = -math.log(1 + score) * SHIELD_INITIAL_SPEED_MULTIPLIER
    # Convert now_ms to update_count using game's timing formula
    update_count = now_ms / (1000.0 / TICKS_PER_SECOND)
    return initial_speed * (1 - (SHIELD_ACCELERATION_RATE ** update_count)) / (1 - SHIELD_ACCELERATION_RATE)


def setup_letter_collision(game: Game, shield_x: int = 100, shield_y: int = 300) -> None:
    """Setup letter for collision testing.

    Args:
        game: Game instance
        shield_x: X position of shield
        shield_y: Y position of shield (letter positioned above this)
    """
    game.letter.pos = [shield_x, shield_y - COLLISION_LETTER_OFFSET]
    game.letter.start(0)
    game.letter.letter = "A"
    game.letter.game_area_offset_y = 0


@async_test
async def test_shield_creation_from_word_scoring():
    """Shield is created when player scores a word via stage_guess."""
    game, _mqtt, _queue = await create_test_game()

    # Initially no shields
    assert len(game.shields) == 0

    # Score a word
    word = "TEST"
    score = 10
    player = 0
    now_ms = 0

    await game.stage_guess(score, word, player, now_ms)

    # Shield should be created
    assert len(game.shields) == 1
    shield = game.shields[0]

    # Verify shield properties
    assert shield.letters == word
    assert shield.score == score
    assert shield.player == player
    assert shield.active is True
    assert shield.start_time_ms == now_ms


@pytest.mark.parametrize("score,label,min_font,max_font", [
    (LOW_SCORE, "small", 12, 14),
    (MEDIUM_SCORE, "medium", 20, 26),
    (HIGH_SCORE, "large", 30, 36),
], ids=["low-score-3pts", "medium-score-15pts", "high-score-50pts"])
@async_test
async def test_shield_sizing(score, label, min_font, max_font):
    """Shield font size scales correctly with score levels."""
    game, _mqtt, _queue = await create_test_game()
    shield = Shield((100, RACK_TOP_Y), "TEST", score, 0, 0)
    expected_size = calculate_expected_font_size(score)

    assert shield.font.size == expected_size
    assert shield.score == score
    assert min_font <= shield.font.size <= max_font, \
        f"Expected {label} font ({min_font}-{max_font}px), got {shield.font.size}px"


@async_test
async def test_shield_font_size_scales_with_score():
    """Shield font size increases monotonically with score."""
    game, _mqtt, _queue = await create_test_game()

    scores = [1, 5, 10, 20, 40, 80]
    font_sizes = []

    for score in scores:
        shield = Shield((100, RACK_TOP_Y), "TEST", score, 0, 0)
        font_sizes.append(shield.font.size)

    # Each font size should be larger than the previous
    for i in range(1, len(font_sizes)):
        delta = font_sizes[i] - font_sizes[i-1]
        assert font_sizes[i] > font_sizes[i-1], \
            f"Font size should increase with score: {scores[i-1]}→{scores[i]} pts = {font_sizes[i-1]}→{font_sizes[i]} px (Δ{delta})"


@async_test
async def test_shield_moves_upward_from_creation():
    """Shield animates upward from its creation position."""
    game, _mqtt, _queue = await create_test_game()

    # Position letter far above screen to prevent collision during animation
    suppress_letter(game)

    base_y = RACK_TOP_Y
    shield = Shield((100, base_y), "SHIELD", 20, 0, 0)
    game.shields.append(shield)

    initial_y = shield.pos[1]

    # Run for several frames - single call to maintain timing continuity
    await advance_frames(game, _queue, frames=30)

    # Shield should have moved upward (negative Y direction)
    upward_distance = initial_y - shield.pos[1]
    assert shield.pos[1] < initial_y, \
        f"Shield should move up: initial={initial_y}px, current={shield.pos[1]}px (moved up {upward_distance:.2f}px), active={shield.active}"


@async_test
async def test_shield_animation_trajectory():
    """Shield follows expected exponential acceleration trajectory."""
    game, _mqtt, _queue = await create_test_game()

    # Position letter far above screen to prevent collision during animation
    suppress_letter(game)

    score = 20
    base_y = RACK_TOP_Y
    shield = Shield((100, base_y), "TRAJECTORY", score, 0, 0)
    game.shields.append(shield)

    initial_base_y = shield.base_pos[1]

    # Test at multiple time points - single continuous simulation
    test_frames = [10, 20, 30, 40]
    test_results = []

    def check_and_record(frame_count, now_ms):
        if frame_count in test_frames:
            test_results.append((frame_count, now_ms, shield.pos[1]))
        return frame_count >= max(test_frames)

    await run_until_condition(game, _queue, check_and_record, max_frames=max(test_frames))

    # Verify trajectory at each checkpoint
    for frame_count, now_ms, actual_y in test_results:
        expected_displacement = calculate_expected_displacement(score, now_ms)
        expected_y = initial_base_y + expected_displacement
        diff = abs(actual_y - expected_y)

        assert diff < TRAJECTORY_TOLERANCE_PX, \
            f"At frame {frame_count} ({now_ms}ms): expected Y={expected_y:.2f}, got {actual_y:.2f}, diff={diff:.2f}px (tolerance={TRAJECTORY_TOLERANCE_PX}px)"


@async_test
async def test_shield_acceleration_over_time():
    """Shield accelerates upward (velocity increases over time)."""
    game, _mqtt, _queue = await create_test_game()

    # Position letter far above screen to prevent collision during animation
    suppress_letter(game)

    shield = Shield((100, RACK_TOP_Y), "ACCEL", 25, 0, 0)
    game.shields.append(shield)

    # Track positions at 10-frame intervals - single continuous simulation
    positions = []
    measurement_intervals = [0, 10, 20, 30, 40, 50]

    def check_and_record(frame_count, now_ms):
        if frame_count in measurement_intervals:
            positions.append(shield.pos[1])
        return frame_count >= max(measurement_intervals)

    await run_until_condition(game, _queue, check_and_record, max_frames=max(measurement_intervals))

    # Calculate velocities (distance moved per 10 frames)
    velocities = []
    for i in range(1, len(positions)):
        velocity = abs(positions[i] - positions[i-1])
        velocities.append(velocity)

    # Velocities should increase (acceleration)
    for i in range(1, len(velocities)):
        velocity_increase = velocities[i] - velocities[i-1]
        assert velocities[i] > velocities[i-1], \
            f"Velocity should increase: interval {i-1}→{i}: {velocities[i-1]:.2f}→{velocities[i]:.2f} px/10frames (Δ{velocity_increase:.2f})"


@async_test
async def test_shield_higher_score_moves_faster():
    """Shields with higher scores have faster initial velocity."""
    game, _mqtt, _queue = await create_test_game()

    low_shield = Shield((100, RACK_TOP_Y), "LOW", 5, 0, 0)
    high_shield = Shield((200, RACK_TOP_Y), "HIGH", 50, 0, 0)

    game.shields.extend([low_shield, high_shield])

    low_initial = low_shield.pos[1]
    high_initial = high_shield.pos[1]

    # Run for same duration
    await advance_frames(game, _queue, frames=20)

    low_distance = abs(low_shield.pos[1] - low_initial)
    high_distance = abs(high_shield.pos[1] - high_initial)

    # High score shield should move farther
    distance_ratio = high_distance / low_distance if low_distance > 0 else float('inf')
    assert high_distance > low_distance, \
        f"High score shield should move more: low(5pts)={low_distance:.2f}px, high(50pts)={high_distance:.2f}px (ratio={distance_ratio:.2f}x)"


@async_test
async def test_shield_initial_speed_formula():
    """Shield initial speed matches formula: -log(1+score) * SHIELD_INITIAL_SPEED_MULTIPLIER."""
    game, _mqtt, _queue = await create_test_game()

    score = 15
    shield = Shield((100, RACK_TOP_Y), "SPEED", score, 0, 0)

    expected_speed = -math.log(1 + score) * SHIELD_INITIAL_SPEED_MULTIPLIER

    assert shield.initial_speed == expected_speed, \
        f"Initial speed should be {expected_speed}, got {shield.initial_speed}"
    assert shield.acceleration_rate == SHIELD_ACCELERATION_RATE, \
        f"Acceleration rate should be {SHIELD_ACCELERATION_RATE}, got {shield.acceleration_rate}"


@async_test
async def test_shield_state_active_to_inactive():
    """Shield transitions from active to inactive on collision."""
    game, _mqtt, _queue = await create_test_game()

    shield_x, shield_y = 100, 300
    shield = Shield((shield_x, shield_y), "STATE", 20, 0, 0)
    game.shields.append(shield)

    # Initially active
    assert shield.active is True

    # Setup letter to collide
    setup_letter_collision(game, shield_x, shield_y)

    # Run until collision
    await run_until_condition(game, _queue, lambda fc, ms: not shield.active)

    # Now inactive
    assert shield.active is False


@async_test
async def test_shield_moves_offscreen_on_deactivation():
    """Shield moves off-screen when deactivated via letter_collision."""
    game, _mqtt, _queue = await create_test_game()

    shield = Shield((100, 300), "OFFSCREEN", 20, 0, 0)

    # Manually trigger deactivation
    shield.letter_collision()

    assert shield.active is False
    # Shield moves to SCREEN_HEIGHT (off-screen position at bottom)
    assert shield.pos[1] == game_config.SCREEN_HEIGHT, \
        f"Shield should move to SCREEN_HEIGHT ({game_config.SCREEN_HEIGHT}), got {shield.pos[1]}"


@async_test
async def test_shield_text_content_preserved():
    """Shield displays the exact word that was scored."""
    game, _mqtt, _queue = await create_test_game()

    test_words = ["CAT", "DOGS", "AMAZING", "Q"]

    for word in test_words:
        shield = Shield((100, 200), word, 10, 0, 0)
        assert shield.letters == word

        # Verify surface was rendered with the word
        assert shield.surface is not None
        assert shield.surface.get_width() > 0


@async_test
async def test_shield_player_ownership():
    """Shield tracks which player created it."""
    game, _mqtt, _queue = await create_test_game()

    # Player 0 shield
    shield_p0 = Shield((100, 200), "P0", 10, 0, 0)
    assert shield_p0.player == 0

    # Player 1 shield
    shield_p1 = Shield((100, 200), "P1", 10, 1, 0)
    assert shield_p1.player == 1


@async_test
async def test_shield_creation_timestamp():
    """Shield records creation time for animation calculations."""
    game, _mqtt, _queue = await create_test_game()

    creation_time = 5000  # 5 seconds
    shield = Shield((100, 200), "TIME", 10, 0, creation_time)

    assert shield.start_time_ms == creation_time


@async_test
async def test_shield_horizontal_centering():
    """Shield horizontally centers itself on screen."""
    game, _mqtt, _queue = await create_test_game()

    # Create shield at arbitrary X position
    shield = Shield((999, 200), "CENTER", 20, 0, 0)

    # Shield should reposition X to center based on surface width
    expected_x = int(game_config.SCREEN_WIDTH / 2 - shield.surface.get_width() / 2)

    assert shield.pos[0] == expected_x, \
        f"Shield should be centered: expected X={expected_x}, got {shield.pos[0]}"


@async_test
async def test_inactive_shield_not_rendered():
    """Inactive shields skip rendering in update method."""
    game, _mqtt, _queue = await create_test_game()

    shield = Shield((100, 200), "INACTIVE", 10, 0, 0)
    game.shields.append(shield)

    # Deactivate shield
    shield.active = False
    shield.pos[1] = game_config.SCREEN_HEIGHT

    # Run a frame with the inactive shield
    await advance_frames(game, _queue, frames=1)

    # Shield should remain inactive and off-screen
    assert shield.active is False
    assert shield.pos[1] >= game_config.SCREEN_HEIGHT


@async_test
async def test_shield_removed_from_list_after_collision():
    """Game state removes inactive shields from the shields list."""
    game, _mqtt, _queue = await create_test_game()

    shield_x, shield_y = 100, 300
    shield = Shield((shield_x, shield_y), "REMOVE", 20, 0, 0)
    game.shields.append(shield)

    assert len(game.shields) == 1

    # Setup letter collision
    setup_letter_collision(game, shield_x, shield_y)

    # Run until collision and cleanup
    await run_until_condition(game, _queue, lambda fc, ms: not shield.active, max_frames=100)

    # Wait one more frame for cleanup
    await advance_frames(game, _queue, frames=2)

    # Shield should be removed from list (GameState.update removes inactive shields)
    assert len(game.shields) == 0, \
        f"Inactive shield should be removed, found {len(game.shields)} shields"
