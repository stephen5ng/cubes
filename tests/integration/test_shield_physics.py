"""Shield Physics Integration Test

Validates that shields correctly intercept falling letters and trigger
bounce physics.

Run with:
    python3 -m pytest tests/integration/test_shield_physics.py
"""
import pytest
import logging
from typing import List

from game.components import Shield
from game.game_state import Game
from config import game_config
from tests.fixtures.game_factory import create_test_game, run_until_condition, advance_frames, async_test
from tests.assertions.game_assertions import assert_word_in_guesses

# Test Constants
SHIELD_X = 100
SHIELD_Y = 400
SHIELD_HEALTH = 100
BOUNCE_DETECTION_THRESHOLD = 50
SHIELD_APPROACH_DISTANCE = 20
SHIELD_PENETRATION_TOLERANCE = 50

logger = logging.getLogger(__name__)


def setup_letter_above_shield(
    game: Game,
    x: int,
    y: int,
    distance: int = SHIELD_APPROACH_DISTANCE
) -> None:
    """Set up letter to fall toward a shield at (x, y).

    Args:
        game: Game instance
        x: Horizontal position
        y: Shield Y position
        distance: Pixels above shield to position letter
    """
    game.letter.start(0)
    game.letter.pos = [x, y - distance]
    game.letter.current_fall_start_y = y - distance
    game.letter.letter = "A"
    game.letter.game_area_offset_y = 0


def setup_rack_with_word(game: Game, player: int, word: str) -> None:
    """Populate player rack with tiles for word.

    Args:
        game: Game instance
        player: Player index (0 or 1)
        word: Word to populate rack with
    """
    from core import tiles
    game._app._rack_manager.get_rack(player).set_tiles(
        [tiles.Tile(c, str(i)) for i, c in enumerate(word)]
    )

@async_test
async def test_shield_collision_bounces_letter():
    """Shield collision causes bounce and deactivation."""
    game, _mqtt, _queue = await create_test_game()

    shield = Shield((SHIELD_X, SHIELD_Y), "SHIELD", SHIELD_HEALTH, 0, 0)
    game.shields.append(shield)

    # Setup falling letter
    game.letter.game_area_offset_y = 0
    setup_letter_above_shield(game, SHIELD_X, SHIELD_Y, distance=0)

    # Run until shield hit
    hit = await run_until_condition(game, _queue, lambda fc, ms: not shield.active)
    assert hit, "Shield was never hit"
    assert not shield.active, "Shield should be inactive"

    # Continue to see bounce
    def tracker(frame_count: int, now_ms: int) -> bool:
        current_y = game.letter.pos[1]
        return current_y < SHIELD_Y - BOUNCE_DETECTION_THRESHOLD

    bounced = await run_until_condition(game, _queue, tracker, max_frames=60)
    assert bounced, f"Letter didn't bounce up (Y={game.letter.pos[1]})"
    assert game.letter.pos[1] < SHIELD_Y

@async_test
async def test_shield_deactivation_on_hit():
    """Verify shield active state deactivates on collision and moves off screen."""
    game, _mqtt, _queue = await create_test_game()
    shield = Shield((SHIELD_X, SHIELD_Y), "TEST", 100, 0, 0)
    game.shields.append(shield)

    setup_letter_above_shield(game, SHIELD_X, SHIELD_Y)

    await run_until_condition(game, _queue, lambda fc, ms: not shield.active)

    assert not shield.active, "Shield should be deactivated after collision"
    assert shield.pos[1] >= game_config.SCREEN_HEIGHT, "Shield should move off screen"

@async_test
async def test_multiple_shields_independent():
    """Verify hitting one shield doesn't affect another."""
    game, _mqtt, _queue = await create_test_game()
    s1 = Shield((SHIELD_X, 400), "S1", 100, 0, 0)
    s2 = Shield((SHIELD_X, 500), "S2", 100, 0, 0)
    game.shields.extend([s1, s2])

    setup_letter_above_shield(game, SHIELD_X, 400)

    await run_until_condition(game, _queue, lambda fc, ms: not s1.active)

    assert not s1.active, "First shield should be deactivated"
    assert s2.active, "Second shield should remain active"

@async_test
async def test_shield_blocks_letter_descent():
    """Verify letter cannot pass through active shield."""
    game, _mqtt, _queue = await create_test_game()
    shield = Shield((SHIELD_X, SHIELD_Y), "WALL", 100, 0, 0)
    game.shields.append(shield)

    setup_letter_above_shield(game, SHIELD_X, SHIELD_Y, distance=100)

    deepest_y = 0
    def track_deepest(frame_count: int, now_ms: int) -> bool:
        nonlocal deepest_y
        deepest_y = max(deepest_y, game.letter.pos[1])
        return not shield.active

    await run_until_condition(game, _queue, track_deepest)

    assert deepest_y < SHIELD_Y + SHIELD_PENETRATION_TOLERANCE, \
        f"Letter penetrated too deep: {deepest_y} (shield at {SHIELD_Y})"


@async_test
async def test_shield_word_in_previous_guesses():
    """Verify shield word is added to previous guesses on collision."""
    game, _mqtt, _queue = await create_test_game()

    word = "SHIELDS"
    # Ensure rack has letters so it's a 'possible' guess
    setup_rack_with_word(game, player=0, word=word)

    shield = Shield((SHIELD_X, SHIELD_Y), word, 50, 0, 0)
    game.shields.append(shield)

    setup_letter_above_shield(game, SHIELD_X, SHIELD_Y)

    # Wait for collision
    await run_until_condition(game, _queue, lambda fc, ms: not shield.active)

    # Wait for event processing
    await advance_frames(game, _queue, frames=10)

    # Verify word in guesses
    assert_word_in_guesses(game, word)
