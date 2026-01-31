# From https://python-forum.io/thread-23029.html

from utils import hub75
import aiofiles
import aiomqtt
import argparse
import asyncio
from datetime import datetime
import easing_functions
from enum import Enum
import json
import logging
import math
import pygame
import pygame.freetype
from pygame import Color
import random
from utils import textrect
from typing import cast
import functools

class EventType(Enum):
    PYGAME = "pygame"
    MQTT = "mqtt"

from core import app
from config import game_config
from hardware import cubes_to_game
from testing.mock_mqtt_client import MockMqttClient
from pygame.image import tobytes as image_to_string
from utils.pygameasync import Clock, events
from core import tiles
from systems.sound_manager import SoundManager
from input.input_devices import (
    InputDevice, CubesInput, KeyboardInput, GamepadInput, DDRInput, 
    JOYSTICK_NAMES_TO_INPUTS
)
from input.input_controller import GameInputController
from rendering.metrics import RackMetrics
from rendering.animations import get_alpha, LetterSource
from game.components import Score, Shield
from config import game_config
from config.game_config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, SCALING_FACTOR,
    TICKS_PER_SECOND, FONT, ANTIALIAS, FONT_SIZE_DELTA, FREE_SCORE,
    LETTER_SOURCE_COLOR,
    RACK_COLOR, SCORE_COLOR,
    REMAINING_PREVIOUS_GUESSES_COLOR, PREVIOUS_GUESSES_COLOR
)
from ui.guess_faders import LastGuessFader, FaderManager
from ui.guess_display import (
    PreviousGuessesDisplayBase,
    PreviousGuessesDisplay,
    RemainingPreviousGuessesDisplay
)
from game.letter import GuessType, Letter
from rendering.rack_display import RackDisplay
from game.game_state import Game
from events.game_events import GameAbortEvent
from game.recorder import FileSystemRecorder, NullRecorder
from game.descent_strategy import DescentStrategy

from game.game_coordinator import GameCoordinator

logger = logging.getLogger(__name__)


from input.input_manager import InputManager
from input.keyboard_handler import KeyboardHandler
from mqtt.mqtt_coordinator import MQTTCoordinator

class BlockWordsPygame:
    def __init__(self,
                 replay_file: str, descent_mode: str, descent_duration_s: int, record: bool, continuous: bool, one_round: bool, min_win_score: int, stars: bool) -> None:
        """
        Args:
            replay_file: Path to replay file, or empty string for live game.
            descent_mode: Mode for letter descent ("discrete" or "timed").
            descent_duration_s: Duration in seconds for descent speed calculation.
            record: Whether to record the game.
        """
        self._window = pygame.display.set_mode(
            (SCREEN_WIDTH*SCALING_FACTOR, SCREEN_HEIGHT*SCALING_FACTOR))
        self.letter_font = pygame.freetype.SysFont(FONT, RackMetrics.LETTER_SIZE)
        self.the_app = None
        self.game = None
        self.running = True
        self.replay_file = replay_file
        self.descent_mode = descent_mode
        self.descent_duration_s = descent_duration_s
        self.record = record
        self.replayer = None
        self.continuous = continuous
        self.one_round = one_round
        self.min_win_score = min_win_score
        self.stars = stars
        self._has_auto_started = False
        
        self.input_manager = InputManager(replay_file)
        self.game_coordinator = GameCoordinator()
        self.keyboard_handler = None  # Initialized in setup_game

    async def _handle_pygame_events(self, pygame_events, keyboard_input, input_devices, now_ms, events_to_log):
        for pygame_event in pygame_events:
            event_type = pygame_event['type']
            if event_type == "QUIT":
                self.game.game_logger.log_events(now_ms, events_to_log)
                self.game.game_logger.stop_logging()
                self.game.output_logger.stop_logging()
                await events.stop()
                return True

            if event_type == "KEYDOWN":
                if (self.min_win_score > 0) and pygame_event['key'] == "ESCAPE":
                    self.game.game_logger.log_events(now_ms, events_to_log)
                    self.game.game_logger.stop_logging()
                    self.game.output_logger.stop_logging()
                    await events.stop()
                    return True

                await self.keyboard_handler.handle_event(pygame_event['key'], keyboard_input, now_ms)
            
            if 'JOY' in event_type:
                for input_device in input_devices: 
                    if str(input_device) == "GamepadInput":
                        await input_device.process_event(pygame_event, now_ms)
        return False

    async def setup_game(self, the_app: app.App, subscribe_client: aiomqtt.Client,
                         publish_queue: asyncio.Queue, game_logger, output_logger):
        """Set up all game components. Returns (screen, keyboard_input, input_devices, mqtt_message_queue, clock)."""
        screen, keyboard_input, input_devices, mqtt_message_queue, clock, self.descent_mode, self.descent_duration_s = await self.game_coordinator.setup_game(
            the_app, subscribe_client, publish_queue, game_logger, output_logger,
            self.input_manager, self.letter_font,
            self.replay_file, self.descent_mode, self.descent_duration_s,
            self.record, self.one_round, self.min_win_score, self.stars
        )
        
        # Hydrate local references
        self.game = self.game_coordinator.game
        self.mqtt_coordinator = self.game_coordinator.mqtt_coordinator
        self.input_controller = self.game_coordinator.input_controller
        self.keyboard_handler = self.game_coordinator.keyboard_handler
        
        return screen, keyboard_input, input_devices, mqtt_message_queue, clock

    async def run_single_frame(self, screen, keyboard_input, input_devices,
                               mqtt_message_queue, publish_queue, time_offset):
        """Run a single frame of the game. Returns (should_exit, new_time_offset, exit_code)."""
        now_ms = pygame.time.get_ticks() + time_offset

        # Handle auto-start for non-continuous mode
        if not self.continuous and not self.replay_file and not self.game.running and not self._has_auto_started:
            print("Auto-starting game (non-continuous mode)")
            keyboard_input.player_number = await self.input_controller.start_game(keyboard_input, now_ms)
            self._has_auto_started = True

        # Handle auto-exit for non-continuous mode (unless game is winnable i.e. has specific win criteria)
        if not self.continuous and not (self.min_win_score > 0) and self._has_auto_started and not self.game.running:
            # Check if post-game animation is done
            time_since_over = (now_ms / 1000.0) - self.game.stop_time_s
            # Wait a bit longer than the animation to ensure it's fully done
            if time_since_over > 2.0:
                print("Game finished and animation complete. Exiting (non-continuous mode).")
                return True, time_offset, self.game.exit_code

        if self.game.aborted:
            await events.stop()
            return True, time_offset, 1

        pygame_events = self.input_manager.get_pygame_events()
        mqtt_events = self.input_manager.get_mqtt_events(mqtt_message_queue)
        events_to_log = {}
        if pygame_events:
            events_to_log['pygame'] = pygame_events

        if mqtt_events:
            events_to_log['mqtt'] = mqtt_events

        if self.input_manager.has_replay_events_remaining():
            now_ms = time_offset = self.input_manager.get_replay_events(pygame_events, mqtt_events)
        elif self.replay_file:
            print("Replay events exhausted. Exiting.")
            return True, time_offset, 0

        if await self._handle_pygame_events(pygame_events, keyboard_input, input_devices, now_ms, events_to_log):
            return True, time_offset, self.game.exit_code

        for mqtt_event in mqtt_events:
            await self.mqtt_coordinator.handle_message(mqtt_event['topic'], mqtt_event['payload'], now_ms)

        # Check if ABC start sequence should be activated
        await cubes_to_game.activate_abc_start_if_ready(publish_queue, now_ms)

        # Check if any ABC countdown has completed
        countdown_incidents = await cubes_to_game.check_countdown_completion(publish_queue, now_ms, self.game.sound_manager)

        screen.fill((0, 0, 0))

        # Collect incidents from game update
        game_incidents = await self.game.update(screen, now_ms)

        # Combine countdown incidents with game incidents
        all_incidents = countdown_incidents + game_incidents

        if len(all_incidents) > 0:
            events_to_log['incidents'] = all_incidents

        if mqtt_events or pygame_events or all_incidents:
            self.game.game_logger.log_events(now_ms, events_to_log)

        hub75.update(screen)
        pygame.transform.scale(screen, self._window.get_rect().size, dest_surface=self._window)
        pygame.display.flip()

        # Yield control to event loop to allow background tasks (like event worker) to run
        await asyncio.sleep(0)

        return False, time_offset, 0

    async def main(self, the_app: app.App, subscribe_client: aiomqtt.Client, start: bool,
                   keyboard_player_number: int, publish_queue: asyncio.Queue,
                   game_logger, output_logger) -> int:
        """Main game loop using production setup."""
        screen, keyboard_input, input_devices, mqtt_message_queue, clock = await self.setup_game(
            the_app, subscribe_client, publish_queue, game_logger, output_logger
        )

        time_offset = 0  # so that time doesn't go backwards after playing a replay file
        while True:
            should_exit, time_offset, exit_code = await self.run_single_frame(
                screen, keyboard_input, input_devices, mqtt_message_queue,
                publish_queue, time_offset
            )
            if should_exit:
                await events.stop()
                return exit_code

            if self.replay_file:
                await asyncio.sleep(0)
            else:
                await clock.tick(TICKS_PER_SECOND)


