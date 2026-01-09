"""Shield Physics Integration Test

Validates that shields correctly intercept falling letters and trigger
bounce physics.

Run with:
    python3 -m pytest tests/test_shield_physics.py

For visual debugging:
    python3 tests/test_shield_physics.py --visual
"""
import argparse
import os
import sys
import pygame
import logging
import asyncio
import pytest
from functools import wraps
from typing import Callable

# Ensure we use dummy driver for headless tests unless overridden
if "SDL_VIDEODRIVER" not in os.environ:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

from core.app import App
from core import dictionary
from game.game_state import Game
from game.components import Shield
from config import game_config
from hardware import cubes_to_game
from rendering.metrics import RackMetrics
from systems.sound_manager import SoundManager
from game_logging.game_loggers import GameLogger, OutputLogger
from testing.fake_mqtt_client import FakeMqttClient
from utils.pygameasync import events

# Test Constants
SHIELD_X = 100
SHIELD_Y = 400
SHIELD_HEALTH = 100
MAX_SIMULATION_FRAMES = 600  # 10s at 60fps
FRAME_DURATION_MS = 16
MIN_BOUNCE_HEIGHT = 200
SHIELD_APPROACH_DISTANCE = 20  # Distance above shield to position letter
SHIELD_PENETRATION_TOLERANCE = 50  # Max penetration depth past shield
BOUNCE_DETECTION_THRESHOLD = 50  # Min upward travel to detect bounce

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def async_test(coro):
    """Decorator to run async tests with asyncio.run()."""
    @wraps(coro)
    def wrapper(*args, **kwargs):
        # We need to manage the event engine lifecycle
        async def run_with_events():
            # Reset queue to bind to current loop
            events.queue = asyncio.Queue()

            # Ensure events engine is running
            if not events.running:
                await events.start()
            try:
                await coro(*args, **kwargs)
            finally:
                await events.stop()

        return asyncio.run(run_with_events())
    return wrapper

async def create_game(descent_mode="discrete", duration_s=120):
    """Factory for common test game setup."""
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()

    real_dictionary = dictionary.Dictionary(game_config.MIN_LETTERS, game_config.MAX_LETTERS)
    fake_mqtt = FakeMqttClient()
    publish_queue = asyncio.Queue()

    app = App(publish_queue, real_dictionary)
    await cubes_to_game.init(fake_mqtt)
    
    # clear initial state
    await cubes_to_game.clear_all_letters(publish_queue, 0)

    rack_metrics = RackMetrics()
    sound_manager = SoundManager()

    game = Game(
        the_app=app,
        letter_font=rack_metrics.font,
        game_logger=GameLogger(None),
        output_logger=OutputLogger(None),
        sound_manager=sound_manager,
        rack_metrics=rack_metrics,
        letter_beeps=sound_manager.get_letter_beeps(),
        descent_mode=descent_mode
    )
    
    # Initialize game state
    game.running = True
    
    return game, fake_mqtt, publish_queue

async def run_until_condition(game: Game, condition: Callable[[], bool], max_frames=MAX_SIMULATION_FRAMES, visual=False):
    """Run the game loop until condition is met or timeout."""
    if not pygame.get_init():
        pygame.init()
    
    # Initialize display if not already done (needed for font rendering etc even in dummy)
    if not pygame.display.get_surface():
        pygame.display.set_mode((game_config.SCREEN_WIDTH, game_config.SCREEN_HEIGHT))

    clock = pygame.time.Clock()
    frame_count = 0
    window = pygame.display.get_surface()

    while frame_count < max_frames:
        if visual:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
            window.fill((0, 0, 0))

        # Update game
        await game.update(window, frame_count * FRAME_DURATION_MS)

        if condition():
            return True

        if visual:
            pygame.display.flip()
            clock.tick(60)
            await asyncio.sleep(0)

        frame_count += 1
    
    return False

async def run_frames(game: Game, frames: int, visual=False):
    """Run for a specific number of frames."""
    await run_until_condition(game, lambda: False, max_frames=frames, visual=visual)

def setup_letter_above_shield(game: Game, x: int, y: int, distance: int = SHIELD_APPROACH_DISTANCE):
    """Position letter above a target point and start its descent."""
    game.letter.pos = [x, y - distance]
    game.letter.start(0)
    game.letter.letter = "A"

# --- Tests ---

@async_test
async def test_shield_collision_bounces_letter():
    """Original test: Shield collision causes bounce and deactivation."""
    game, _mqtt, _queue = await create_game()

    shield = Shield((SHIELD_X, SHIELD_Y), "SHIELD", SHIELD_HEALTH, 0, 0)
    game.shields.append(shield)

    # Setup falling letter
    game.letter.game_area_offset_y = 0
    setup_letter_above_shield(game, SHIELD_X, SHIELD_Y, distance=0)

    # Run until shield hit
    hit = await run_until_condition(game, lambda: not shield.active)
    assert hit, "Shield was never hit"
    assert not shield.active, "Shield should be inactive"

    # Continue to see bounce
    min_y = game.letter.pos[1]

    def tracker():
        nonlocal min_y
        current_y = game.letter.pos[1]
        if current_y < min_y:
            min_y = current_y
        # Stop if we bounced up significantly
        return current_y < SHIELD_Y - BOUNCE_DETECTION_THRESHOLD

    bounced = await run_until_condition(game, tracker, max_frames=60)
    assert game.letter.pos[1] < SHIELD_Y, f"Letter didn't bounce up (Y={game.letter.pos[1]})"

@async_test
async def test_shield_deactivation_on_hit():
    """Verify shield active state deactivates on collision and moves off screen."""
    game, _mqtt, _queue = await create_game()
    shield = Shield((SHIELD_X, SHIELD_Y), "TEST", 100, 0, 0)
    game.shields.append(shield)

    setup_letter_above_shield(game, SHIELD_X, SHIELD_Y)

    # Run until collision
    await run_until_condition(game, lambda: not shield.active)

    assert not shield.active, "Shield should be deactivated after collision"
    # Upon deactivation, shield moves to SCREEN_HEIGHT to get out of the way
    assert shield.pos[1] >= game_config.SCREEN_HEIGHT, "Shield should move off screen"

@async_test
async def test_multiple_shields_independent():
    """Verify hitting one shield doesn't affect another."""
    game, _mqtt, _queue = await create_game()
    # Place shields at different Y levels
    s1 = Shield((SHIELD_X, 400), "S1", 100, 0, 0)
    s2 = Shield((SHIELD_X, 500), "S2", 100, 0, 0)
    game.shields.extend([s1, s2])

    # Target S1 at 400
    setup_letter_above_shield(game, SHIELD_X, 400)

    # Wait for S1 hit
    await run_until_condition(game, lambda: not s1.active)

    assert not s1.active, "First shield should be deactivated"
    assert s2.active, "Second shield should remain active"

@pytest.mark.skip(reason="Requires fixing global EventEngine state management in tests")
@async_test
async def test_shield_word_in_previous_guesses():
    """Verify shield word is added to guesses when hit."""
    game, _mqtt, _queue = await create_game()
    shield = Shield((SHIELD_X, SHIELD_Y), "MAGIC", 100, 0, 0)
    game.shields.append(shield)

    setup_letter_above_shield(game, SHIELD_X, SHIELD_Y)

    # We must wait long enough for the event to be processed
    # EventEngine works in background, so after condition met, we might need a small tick
    await run_until_condition(game, lambda: not shield.active)
    await asyncio.sleep(0.1)  # Let events propagate

    guesses = game.guesses_manager.previous_guesses_display.previous_guesses + \
              game.guesses_manager.remaining_previous_guesses_display.remaining_guesses
    assert "MAGIC" in guesses, "Shield word should appear in previous guesses"

@async_test
async def test_shield_blocks_letter_descent():
    """Verify letter cannot pass through active shield."""
    game, _mqtt, _queue = await create_game()
    shield = Shield((SHIELD_X, SHIELD_Y), "WALL", 100, 0, 0)
    game.shields.append(shield)

    setup_letter_above_shield(game, SHIELD_X, SHIELD_Y, distance=100)

    # Track deepest Y position reached (higher Y = lower on screen)
    deepest_y = 0

    def track_deepest():
        nonlocal deepest_y
        deepest_y = max(deepest_y, game.letter.pos[1])
        return not shield.active  # Stop when shield breaks

    await run_until_condition(game, track_deepest)

    # Letter should bounce before penetrating too far past shield
    assert deepest_y < SHIELD_Y + SHIELD_PENETRATION_TOLERANCE, \
        f"Letter penetrated too deep: {deepest_y} (shield at {SHIELD_Y})"

# --- Visual Runner ---

async def run_visual_demo():
    """Run visual demonstration of shield physics."""
    print("Running visual demo...")
    os.environ.pop("SDL_VIDEODRIVER", None)  # Ensure we use real driver

    # Manually start events for standalone run
    await events.start()
    try:
        game, _mqtt, _queue = await create_game()
        shield = Shield((SHIELD_X, SHIELD_Y), "DEMO", 100, 0, 0)
        game.shields.append(shield)

        setup_letter_above_shield(game, SHIELD_X, SHIELD_Y, distance=0)

        await run_until_condition(game, lambda: not shield.active, visual=True)
        await run_frames(game, 60, visual=True)
        print("Demo complete")
    finally:
        await events.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--visual", action="store_true")
    args = parser.parse_args()
    
    if args.visual:
        asyncio.run(run_visual_demo())
    else:
        # If run as script without visual, run the main test
        asyncio.run(test_shield_collision_bounces_letter())
        print("Test passed!")
