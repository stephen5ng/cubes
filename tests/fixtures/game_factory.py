import os
import asyncio
import inspect
import pygame
import logging
from functools import wraps
from typing import Callable, Optional, Tuple

from core.app import App
from core import dictionary
from game.game_state import Game
from config import game_config
from hardware import cubes_to_game
from rendering.metrics import RackMetrics
from systems.sound_manager import SoundManager
from game_logging.game_loggers import GameLogger, OutputLogger
from testing.fake_mqtt_client import FakeMqttClient
from utils.pygameasync import events

logger = logging.getLogger(__name__)

FRAME_DURATION_MS = 16
MAX_SIMULATION_FRAMES = 600

from contextvars import ContextVar

class MockTime:
    def __init__(self):
        self.now_ms = 0
    def get_ticks(self):
        return self.now_ms

mock_time_var: ContextVar[MockTime] = ContextVar("mock_time")

def get_mock_time() -> MockTime:
    """Get the current mock time instance."""
    return mock_time_var.get()

def is_visual_mode() -> bool:
    """Check if visual mode is enabled via pytest's --visual flag."""
    try:
        import pytest
        # Use pytest.config.getoption if possible, or Fallback to env
        return pytest.config.getoption("--visual")
    except (AttributeError, ImportError):
        return os.environ.get("VISUAL_MODE") == "1"

def async_test(coro):
    """Decorator to run async tests with asyncio.run() and manage EventEngine."""
    from unittest.mock import patch
    @wraps(coro)
    def wrapper(*args, **kwargs):
        async def run_with_events():
            mock_time = MockTime()
            token = mock_time_var.set(mock_time)
            # Reset queue to bind to current loop
            events.queue = asyncio.Queue()

            # Ensure events engine is running
            if not events.running:
                await events.start()
            
            with patch('pygame.time.get_ticks', side_effect=mock_time.get_ticks):
                try:
                    await coro(*args, **kwargs)
                finally:
                    await events.stop()
                    mock_time_var.reset(token)

        return asyncio.run(run_with_events())
    return wrapper

async def create_test_game(descent_mode: str = "discrete", visual: Optional[bool] = None) -> Tuple[Game, FakeMqttClient, asyncio.Queue]:
    """Factory for common test game setup."""
    if visual is None:
        visual = is_visual_mode()

    if visual:
        os.environ.pop("SDL_VIDEODRIVER", None)
    elif "SDL_VIDEODRIVER" not in os.environ:
        os.environ["SDL_VIDEODRIVER"] = "dummy"

    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()

    real_dictionary = dictionary.Dictionary(game_config.MIN_LETTERS, game_config.MAX_LETTERS)
    fake_mqtt = FakeMqttClient()
    publish_queue = asyncio.Queue()

    app = App(publish_queue, real_dictionary)
    await cubes_to_game.init(fake_mqtt)
    
    # Clear initial state
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

def suppress_letter(game: Game) -> None:
    """Effectively disables the falling letter by moving it far off screen.

    Useful for tests that focus on shield animation without collision interference.

    Args:
        game: Game instance to modify
    """
    game.letter.pos = [0, 0]
    game.letter.game_area_offset_y = -2000
    game.letter.letter = ""

async def run_until_condition(
    game: Game, 
    publish_queue: asyncio.Queue,
    condition: Callable[[], bool] | Callable[[int, int], bool], 
    max_frames: int = MAX_SIMULATION_FRAMES, 
    visual: Optional[bool] = None
) -> bool:
    """Run the game loop until condition is met or timeout.

    Args:
        game: Game instance
        publish_queue: MQTT publish queue
        condition: Either `lambda: bool` or `lambda frame_count, now_ms: bool`
        max_frames: Maximum frames to run before timeout
        visual: Enable visual display mode

    Returns:
        True if condition met, False if timeout
    """
    if visual is None:
        visual = is_visual_mode()
    if not pygame.display.get_surface():
        pygame.display.set_mode((game_config.SCREEN_WIDTH, game_config.SCREEN_HEIGHT))

    # Normalize callback to always accept (frame_count, now_ms)
    # Check arity once at start, not every iteration
    sig = inspect.signature(condition)
    if len(sig.parameters) == 0:
        normalized_condition = lambda fc, ms: condition()
    else:
        normalized_condition = condition

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
        now_ms = frame_count * FRAME_DURATION_MS
        # Update patched time
        try:
            mock_time = mock_time_var.get()
            mock_time.now_ms = now_ms
        except LookupError:
            pass

        countdown_incidents = await cubes_to_game.check_countdown_completion(publish_queue, now_ms, game.sound_manager)
        game_incidents = await game.update(window, now_ms)

        # Check condition with normalized callback
        if normalized_condition(frame_count, now_ms):
            return True

        if visual:
            pygame.display.flip()
            clock.tick(60)
            await asyncio.sleep(0)

        frame_count += 1
    
    return False

async def advance_frames(game: Game, publish_queue: asyncio.Queue, frames: int, visual: Optional[bool] = None):
    """Run for a specific number of frames."""
    if visual is None:
        visual = is_visual_mode()
    await run_until_condition(game, publish_queue, lambda: False, max_frames=frames, visual=visual)
