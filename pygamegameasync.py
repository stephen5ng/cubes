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
from rendering.metrics import RackMetrics
from rendering.animations import get_alpha, LetterSource
from game.components import Score, Shield
from config import game_config
from config.game_config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, SCALING_FACTOR,
    TICKS_PER_SECOND, FONT, ANTIALIAS, FONT_SIZE_DELTA, FREE_SCORE,
    BAD_GUESS_COLOR, GOOD_GUESS_COLOR, OLD_GUESS_COLOR, LETTER_SOURCE_COLOR,
    RACK_COLOR, SHIELD_COLOR_P0, SHIELD_COLOR_P1, SCORE_COLOR,
    FADER_COLOR_P0, FADER_COLOR_P1,
    REMAINING_PREVIOUS_GUESSES_COLOR, PREVIOUS_GUESSES_COLOR,
    PLAYER_COLORS, FADER_PLAYER_COLORS
)
from testing.game_replayer import GameReplayer
from ui.guess_faders import LastGuessFader, FaderManager
from ui.guess_display import (
    PreviousGuessesDisplayBase,
    PreviousGuessesDisplay,
    RemainingPreviousGuessesDisplay
)
from game.letter import GuessType, Letter
from rendering.rack_display import Rack
from game.game_state import Game
from events.game_events import GameAbortEvent

logger = logging.getLogger(__name__)


# get_alpha function moved to src/rendering/animations.py
# GuessType enum moved to src/game/letter.py
# Input device classes moved to src/input/input_devices.py
# RackMetrics class moved to src/rendering/metrics.py
# Letter class moved to src/game/letter.py
# Rack class moved to src/rendering/rack_display.py
# Game class moved to src/game/game_state.py


class BlockWordsPygame:
    def __init__(self, replay_file: str, descent_mode: str = "discrete", timed_duration_s: int = 240) -> None:
        self._window = pygame.display.set_mode(
            (SCREEN_WIDTH*SCALING_FACTOR, SCREEN_HEIGHT*SCALING_FACTOR))
        self.letter_font = pygame.freetype.SysFont(FONT, RackMetrics.LETTER_SIZE)
        self.the_app = None
        self.game = None
        self.replay_file = replay_file
        self.descent_mode = descent_mode
        self.timed_duration_s = timed_duration_s
        self.replayer = None
        self._mock_mqtt_client = None

    def get_mock_mqtt_client(self):
        """Get the mock MQTT client for replay mode."""
        if not self._mock_mqtt_client and self.replay_file:
            self.replayer = GameReplayer(self.replay_file)
            self.replayer.load_events()
            # Create mock client with MQTT events only
            # print(f"self.replayer.events: {self.replayer.events}")
            mqtt_events = [e for e in self.replayer.events if hasattr(e, 'mqtt')]
            self._mock_mqtt_client = MockMqttClient(mqtt_events)
        return self._mock_mqtt_client

    async def handle_mqtt_message(self, topic_str: str, payload, now_ms: int) -> None:
        # print(f"{now_ms} Handling message: {topic_str} {payload}")
        if topic_str == "app/start":
            print("Starting due to topic")
            await self.game.start_cubes(now_ms)
        elif topic_str == "app/abort":
            events.trigger(GameAbortEvent())
        elif topic_str == "game/guess":
            payload_str = payload.decode() if payload else ""
            await self.the_app.guess_word_keyboard(payload_str, 1, now_ms)
        elif topic_str.startswith("cube/right/"):
            # Handle None payload by converting to empty string
            # payload_data = payload.decode() if payload is not None else ""
            # Create a simple message-like object for cubes_to_game
            message = type('Message', (), {
                'topic': type('Topic', (), {'value': topic_str})(),
                'payload': payload.encode() if payload is not None else b''
            })()
            # print(f"!!!-----> message: {message}")
            await cubes_to_game.handle_mqtt_message(self._publish_queue, message, now_ms, self.game.sound_manager)

    async def handle_space_action(self, input_device: InputDevice, now_ms: int):
        if not self.game.running:
            return

        rack = self.game.racks[input_device.player_number]
        rack_position = rack.cursor_position if not input_device.reversed else 5 - rack.cursor_position
        if rack_position >= len(input_device.current_guess):
            # Insert letter at cursor position into the guess
            letter_at_cursor = rack.letters()[rack.cursor_position]
            input_device.current_guess += letter_at_cursor
            self.game.sound_manager.play_add()
        else:
            # Remove letter at cursor position from the guess
            if input_device.reversed:
                letter_to_remove = len(input_device.current_guess) - rack_position
                input_device.current_guess = input_device.current_guess[:letter_to_remove-1] + input_device.current_guess[letter_to_remove:]
            else:
                letter_to_remove = rack_position
                input_device.current_guess = input_device.current_guess[:letter_to_remove] + input_device.current_guess[letter_to_remove + 1:]
            if rack.select_count > 0:
                self.game.sound_manager.play_erase()
        rack.select_count = len(input_device.current_guess)
        if rack.select_count == 0:
            self.game.sound_manager.play_cleared()
        await self.the_app.guess_word_keyboard(input_device.current_guess, input_device.player_number, now_ms)

    async def handle_insert_action(self, input_device: InputDevice, now_ms: int):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]            
        if input_device.reversed != (rack.cursor_position >= len(input_device.current_guess)):
            # Insert letter at cursor position into the guess
            letter_at_cursor = rack.letters()[rack.cursor_position]
            input_device.current_guess += letter_at_cursor
            self.game.sound_manager.play_add()
        await self.the_app.guess_word_keyboard(input_device.current_guess, input_device.player_number, now_ms)
    
    async def handle_delete_action(self, input_device: InputDevice, now_ms: int):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]
        if input_device.reversed != (rack.cursor_position < len(input_device.current_guess)):
            # Remove letter at cursor position from the guess
            input_device.current_guess = input_device.current_guess[:rack.cursor_position] + input_device.current_guess[rack.cursor_position + 1:]
            if rack.select_count > 0:
                self.game.sound_manager.play_erase()
        rack.select_count = len(input_device.current_guess)
        if rack.select_count == 0:
            self.game.sound_manager.play_cleared()
        await self.the_app.guess_word_keyboard(input_device.current_guess, input_device.player_number, now_ms)
    
    async def start_game(self, input_device: InputDevice, now_ms: int):
        print(f"=========start_game {input_device} {now_ms}")
        input_device.current_guess = ""
        player_number = await self.game.start(input_device, now_ms)
        rack = self.game.racks[player_number]
        rack.cursor_position = 0
        rack.select_count = 0

        # clear out the last guess
        await self.the_app.guess_word_keyboard("", player_number, now_ms)
        return player_number
    
    def handle_left_movement(self, input_device: InputDevice):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]            
        if rack.cursor_position > 0:
            rack.cursor_position -= 1
            rack.draw()
            self.game.sound_manager.play_left()
    
    def handle_right_movement(self, input_device: InputDevice):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]
        if rack.cursor_position < tiles.MAX_LETTERS - 1:
            rack.cursor_position += 1
            rack.draw()
            self.game.sound_manager.play_right()
    
    def handle_return_action(self, input_device: InputDevice):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]
        input_device.current_guess = ""
        rack.cursor_position = 0 if not input_device.reversed else 5
        rack.select_count = len(input_device.current_guess)
        self.game.sound_manager.play_cleared()
        rack.draw()

    async def handle_keyboard_event(self, key: str, keyboard_input: KeyboardInput, now_ms: int) -> None:
        """Handle keyboard events for the game."""
        if key == "ESCAPE":
            print("starting due to ESC")
            keyboard_input.player_number = await self.start_game(keyboard_input, now_ms)
            return

        if keyboard_input.player_number is None:
            return

        if key == "LEFT":
            self.handle_left_movement(keyboard_input)
        elif key == "RIGHT":
            self.handle_right_movement(keyboard_input)
        elif key == "SPACE":
            await self.handle_space_action(keyboard_input, now_ms)
        elif key == "BACKSPACE":
            if keyboard_input.current_guess:
                keyboard_input.current_guess = keyboard_input.current_guess[:-1]
                self.game.racks[keyboard_input.player_number].select_count = len(keyboard_input.current_guess)
                self.game.racks[keyboard_input.player_number].draw()
        elif key == "RETURN":
            self.handle_return_action(keyboard_input)
        elif key == "TAB":
            self.the_app.player_count = 1 if self.the_app.player_count == 2 else 2
            for player in range(game_config.MAX_PLAYERS):
                self.game.scores[player].draw()
                self.game.racks[player].draw()
        elif len(key) == 1:
            # print(f"player_number: {keyboard_input.player_number}")
            remaining_letters = list(self.game.racks[keyboard_input.player_number].letters())
            for l in keyboard_input.current_guess:
                if l in remaining_letters:
                    remaining_letters.remove(l)
            if key not in remaining_letters:
                keyboard_input.current_guess = ""
                self.game.racks[keyboard_input.player_number].select_count = len(keyboard_input.current_guess)
                remaining_letters = list(self.game.racks[keyboard_input.player_number].letters())
            if key in remaining_letters:
                keyboard_input.current_guess += key
                await self.the_app.guess_word_keyboard(keyboard_input.current_guess, keyboard_input.player_number, now_ms)
                self.game.racks[keyboard_input.player_number].select_count = len(keyboard_input.current_guess)
                logger.info(f"key: {str(key)} {keyboard_input.current_guess}")

    def _get_mqtt_events(self, mqtt_message_queue: asyncio.Queue) -> list:
        mqtt_events = []
        try:
            while not mqtt_message_queue.empty():
                mqtt_message = mqtt_message_queue.get_nowait()
                event = {'topic': str(mqtt_message.topic),
                         'payload': mqtt_message.payload.decode() if mqtt_message.payload else None}
                # print(f"adding to quee {event}")
                mqtt_events.append(event)
        except asyncio.QueueEmpty:
            pass
        return mqtt_events

    def _get_pygame_events(self):
        pygame_events = []
        for pygame_event in pygame.event.get():
            if pygame_event.type == pygame.QUIT:
                pygame_events.append({"type": "QUIT"})
            elif pygame_event.type == pygame.KEYDOWN:
                pygame_events.append({
                    "type": "KEYDOWN",
                    "key": pygame.key.name(pygame_event.key).upper()
                })
            elif pygame_event.type == pygame.JOYAXISMOTION:
                pygame_events.append({
                    "type": "JOYAXISMOTION",
                    "axis": pygame_event.axis,
                    "value": pygame_event.value
                })
            elif pygame_event.type == pygame.JOYBUTTONDOWN:
                pygame_events.append({
                    "type": "JOYBUTTONDOWN",
                    "button": pygame_event.button,
                })
        return pygame_events

    def _get_replay_events(self, pygame_events: list, mqtt_events: list) -> int:
        replay_events = self.replayer.events.pop()
        now_ms = replay_events['timestamp_ms']
        if 'pygame' in replay_events['events']:
            pygame_events.extend(replay_events['events']['pygame'])
        if 'mqtt' in replay_events['events']:
            mqtt_events.extend(replay_events['events']['mqtt'])
        return now_ms

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
                await self.handle_keyboard_event(pygame_event['key'], keyboard_input, now_ms)
            
            if 'JOY' in event_type:
                for input_device in input_devices: 
                    if str(input_device) == "GamepadInput":
                        await input_device.process_event(pygame_event, now_ms)
        return False

    async def setup_game(self, the_app: app.App, subscribe_client: aiomqtt.Client,
                         publish_queue: asyncio.Queue, game_logger, output_logger):
        """Set up all game components. Returns (screen, keyboard_input, input_devices, mqtt_message_queue, clock)."""
        self.the_app = the_app
        self._publish_queue = publish_queue

        # Define handlers dictionary before joystick initialization
        handlers = {
            'left': self.handle_left_movement,
            'right': self.handle_right_movement,
            'insert': self.handle_insert_action,
            'delete': self.handle_delete_action,
            'action': self.handle_space_action,
            'return': self.handle_return_action,
            'start': self.start_game,
        }
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        clock = Clock()

        self.replayer = GameReplayer(self.replay_file)
        if self.replay_file:
            self.replayer.load_events()
            print(f"Replay mode: loaded {len(self.replayer.events)} events from {self.replay_file}")
            mqtt_client = self.get_mock_mqtt_client()
        else:
            await subscribe_client.subscribe("app/#")
            mqtt_client = subscribe_client

        keyboard_input = KeyboardInput(handlers)
        input_devices = [keyboard_input]
        print(f"joystick count: {pygame.joystick.get_count()}")
        if self.replay_file:
            input_devices.append(GamepadInput(handlers))
        elif pygame.joystick.get_count() > 0:
            for j in range(pygame.joystick.get_count()):
                joystick = pygame.joystick.Joystick(j)
                name = joystick.get_name()
                print(f"Game controller connected: {name}")
                input_device = JOYSTICK_NAMES_TO_INPUTS[name](handlers)
                input_device.id = j
                input_devices.append(input_device)

        # Create dependencies for injection
        sound_manager = SoundManager()
        rack_metrics = RackMetrics()

        # Get letter beeps from sound manager for injection into Game
        self.game = Game(the_app, self.letter_font, game_logger, output_logger, sound_manager,
                        rack_metrics, sound_manager.get_letter_beeps(),
                        descent_mode=self.descent_mode, timed_duration_s=self.timed_duration_s)

        self.game.output_logger.start_logging()
        the_app.set_game_logger(self.game.game_logger)
        the_app.set_word_logger(self.game.output_logger)

        # Start the event engine
        await events.start()

        # Signal that the game is ready to receive MQTT messages
        if self.replay_file and self._mock_mqtt_client:
            self._mock_mqtt_client.set_game_ready()

        mqtt_message_queue = asyncio.Queue()
        if not self.replay_file:
            asyncio.create_task(self._process_mqtt_messages(
                mqtt_client, mqtt_message_queue, publish_queue), name="mqtt processor")

        return screen, keyboard_input, input_devices, mqtt_message_queue, clock

    async def run_single_frame(self, screen, keyboard_input, input_devices,
                               mqtt_message_queue, publish_queue, time_offset):
        """Run a single frame of the game. Returns (should_exit, new_time_offset)."""
        now_ms = pygame.time.get_ticks() + time_offset

        if self.game.aborted:
            await events.stop()
            return True, time_offset

        pygame_events = self._get_pygame_events()
        mqtt_events = self._get_mqtt_events(mqtt_message_queue)
        events_to_log = {}
        if pygame_events:
            events_to_log['pygame'] = pygame_events

        if mqtt_events:
            events_to_log['mqtt'] = mqtt_events

        if self.replayer.events:
            now_ms = time_offset = self._get_replay_events(pygame_events, mqtt_events)

        if await self._handle_pygame_events(pygame_events, keyboard_input, input_devices, now_ms, events_to_log):
            return True, time_offset

        for mqtt_event in mqtt_events:
            await self.handle_mqtt_message(mqtt_event['topic'], mqtt_event['payload'], now_ms)

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

        return False, time_offset

    async def main(self, the_app: app.App, subscribe_client: aiomqtt.Client, start: bool,
                   keyboard_player_number: int, publish_queue: asyncio.Queue,
                   game_logger, output_logger) -> None:
        """Main game loop using production setup."""
        screen, keyboard_input, input_devices, mqtt_message_queue, clock = await self.setup_game(
            the_app, subscribe_client, publish_queue, game_logger, output_logger
        )

        time_offset = 0  # so that time doesn't go backwards after playing a replay file
        while True:
            should_exit, time_offset = await self.run_single_frame(
                screen, keyboard_input, input_devices, mqtt_message_queue,
                publish_queue, time_offset
            )
            if should_exit:
                await events.stop()
                return

            if self.replay_file:
                await asyncio.sleep(0)
            else:
                await clock.tick(TICKS_PER_SECOND)

    async def _process_mqtt_messages(self, mqtt_client: aiomqtt.Client, message_queue: asyncio.Queue, publish_queue: asyncio.Queue) -> None:
        """Process MQTT messages and add them to the polling queue for main loop processing."""
        try:
            async for message in mqtt_client.messages:
                await message_queue.put(message)
        except aiomqtt.exceptions.MqttError:
            # This is expected when the client disconnects, so we can ignore it.
            pass
        except Exception as e:
            print(f"MQTT processing error: {e}")
            events.trigger(GameAbortEvent())
            raise e
