# From https://python-forum.io/thread-23029.html

from blockwords.utils import hub75
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
from blockwords.utils import textrect
from typing import cast
import functools

class EventType(Enum):
    PYGAME = "pygame"
    MQTT = "mqtt"

from blockwords.core import app
from blockwords.core.config import MAX_PLAYERS
from blockwords.hardware import cubes_to_game
from blockwords.testing.mock_mqtt_client import MockMqttClient
from pygame.image import tobytes as image_to_string
from blockwords.utils.pygameasync import Clock, events
from blockwords.core import tiles
from src.systems.sound_manager import SoundManager
from src.input.input_devices import (
    InputDevice, CubesInput, KeyboardInput, GamepadInput, DDRInput, 
    JOYSTICK_NAMES_TO_INPUTS
)
from src.rendering.metrics import RackMetrics
from src.rendering.animations import get_alpha, LetterSource
from src.game.components import Score, Shield
from src.config.display_constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, SCALING_FACTOR,
    TICKS_PER_SECOND, FONT, ANTIALIAS, FONT_SIZE_DELTA, FREE_SCORE,
    BAD_GUESS_COLOR, GOOD_GUESS_COLOR, OLD_GUESS_COLOR, LETTER_SOURCE_COLOR,
    RACK_COLOR, SHIELD_COLOR_P0, SHIELD_COLOR_P1, SCORE_COLOR,
    FADER_COLOR_P0, FADER_COLOR_P1,
    REMAINING_PREVIOUS_GUESSES_COLOR, PREVIOUS_GUESSES_COLOR,
    PLAYER_COLORS, FADER_PLAYER_COLORS
)
from src.testing.game_replayer import GameReplayer
from src.ui.guess_faders import LastGuessFader, FaderManager
from src.ui.guess_display import (
    PreviousGuessesDisplayBase,
    PreviousGuessesDisplay,
    RemainingPreviousGuessesDisplay
)
from src.game.letter import GuessType, Letter
from src.rendering.rack_display import Rack

logger = logging.getLogger(__name__)

# Global reference to letter beeps - populated by SoundManager
letter_beeps: list = []


# get_alpha function moved to src/rendering/animations.py
# GuessType enum moved to src/game/letter.py
# Input device classes moved to src/input/input_devices.py
# RackMetrics class moved to src/rendering/metrics.py
# Letter class moved to src/game/letter.py
# Rack class moved to src/rendering/rack_display.py


class Game:
    def __init__(self, 
                 the_app: app.App, 
                 letter_font: pygame.freetype.Font, 
                 game_logger, 
                 output_logger,
                 sound_manager: SoundManager,
                 rack_metrics: RackMetrics) -> None:
        self._app = the_app
        self.game_logger = game_logger
        self.output_logger = output_logger
        
        # Required dependency injection - no defaults!
        self.sound_manager = sound_manager
        self.rack_metrics = rack_metrics
        
        # Populate global letter_beeps from sound manager (temporary until we remove global)
        global letter_beeps
        letter_beeps = self.sound_manager.get_letter_beeps()
        
        # Now create components that depend on injected dependencies
        self.scores = [Score(the_app, player, self.rack_metrics) for player in range(MAX_PLAYERS)]
        letter_y = self.scores[0].get_size()[1] + 4
        self.letter = Letter(letter_font, letter_y, self.rack_metrics, self.output_logger, letter_beeps)
        self.racks = [Rack(the_app, self.rack_metrics, self.letter, player) for player in range(MAX_PLAYERS)]
        self.guess_to_player = {}
        self.previous_guesses_display = PreviousGuessesDisplay(PreviousGuessesDisplay.FONT_SIZE, self.guess_to_player)
        self.remaining_previous_guesses_display = RemainingPreviousGuessesDisplay(
            PreviousGuessesDisplay.FONT_SIZE - FONT_SIZE_DELTA, self.guess_to_player)
        self.letter_source = LetterSource(
            self.letter,
            self.rack_metrics.get_rect().x, self.rack_metrics.get_rect().width,
            letter_y)
        self.shields: list[Shield] = []
        self.running = False
        self.aborted = False
        self.game_log_f = open("output/gamelog.csv", "w")
        self.duration_log_f = open("output/durationlog.csv", "w")
        self.input_devices = []
        self.last_lock = False

        # TODO(sng): remove f
        events.on(f"game.stage_guess")(self.stage_guess)
        events.on(f"game.old_guess")(self.old_guess)
        events.on(f"game.bad_guess")(self.bad_guess)
        events.on(f"game.next_tile")(self.next_tile)
        events.on(f"game.abort")(self.abort)
        events.on(f"game.start")(self.start_cubes)
        events.on(f"game.start_player")(self.start_cubes_player)
        events.on(f"input.remaining_previous_guesses")(self.update_remaining_guesses)
        events.on(f"input.update_previous_guesses")(self.update_previous_guesses)
        events.on(f"input.add_guess")(self.add_guess)
        events.on(f"rack.update_rack")(self.update_rack)
        events.on(f"rack.update_letter")(self.update_letter)

    async def update_rack(self, tiles: list[tiles.Tile], highlight_length: int, guess_length: int, player: int, now_ms: int) -> None:
        await self.racks[player].update_rack(tiles, highlight_length, guess_length, now_ms)

    async def update_letter(self, changed_tile: tiles.Tile, player: int, now_ms: int) -> None:
        await self.racks[player].update_letter(changed_tile, now_ms)

    async def old_guess(self, old_guess: str, player: int, now_ms: int) -> None:
        self.racks[player].guess_type = GuessType.OLD
        self.previous_guesses_display.old_guess(old_guess, now_ms)

    async def bad_guess(self, player: int) -> None:
        self.racks[player].guess_type = GuessType.BAD

    async def abort(self) -> None:
        self.aborted = True

    async def start_cubes(self, now_ms: int) -> None:
        await self.start(CubesInput(None), now_ms)

    async def start_cubes_player(self, now_ms: int, player: int) -> None:
        # Create player-specific CubesInput to enable proper 2-player mode
        cubes_input = CubesInput(None)
        cubes_input.id = f"player_{player}"
        print(f"Starting cubes for player {player} with input device: {cubes_input.id}")
        await self.start(cubes_input, now_ms)

    async def start(self, input_device: InputDevice, now_ms: int) -> None:
        if self.running:
            if str(input_device) not in self.input_devices:
                # Add P2
                print(f"self.running: {self.running}, {str(input_device) in self.input_devices}, {self.input_devices}")
                print(f"starting second player with input_device: {input_device}, {self.input_devices}")
                # Maxed out player count
                if self._app.player_count >= 2:
                    return -1

                self._app.player_count = 2
                self.input_devices.append(str(input_device))
                for player in range(2):
                    self.scores[player].draw()
                    self.racks[player].draw()
                # Load letters for both players when entering 2-player mode
                await self._app.load_rack(now_ms)
                return 1
    
        self._app.player_count = 1
        print(f"{now_ms} starting new game with input_device: {input_device}")
        self.input_devices = [str(input_device)]
        print(f"ADDED {str(input_device)} in self.input_devices: {str(input_device) in self.input_devices}")
        self.guess_to_player = {}
        self.previous_guesses_display = PreviousGuessesDisplay(PreviousGuessesDisplay.FONT_SIZE, self.guess_to_player)
        self.remaining_previous_guesses_display = RemainingPreviousGuessesDisplay(
            PreviousGuessesDisplay.FONT_SIZE - FONT_SIZE_DELTA, self.guess_to_player)
        print(f"start_cubes: starting letter {now_ms}")
        self.letter.start(now_ms)
        for score in self.scores:
            score.start()
        for rack in self.racks:
            rack.start()
        self.running = True
        now_s = now_ms / 1000
        self.stop_time_s = -1000
        self.last_letter_time_s = now_s
        self.start_time_s = now_s
        await self._app.start(now_ms)
        self.sound_manager.play_start()
        print("start done")
        return 0

    async def stage_guess(self, score: int, last_guess: str, player: int, now_ms: int) -> None:
        await self.sound_manager.queue_word_sound(last_guess, player)
        self.racks[player].guess_type = GuessType.GOOD
        self.shields.append(Shield(self.rack_metrics.get_rect().topleft, last_guess, score, player, now_ms))

    async def accept_letter(self, now_ms: int) -> None:
        await self._app.accept_new_letter(self.letter.letter, self.letter.letter_index(), now_ms)
        self.letter.letter = ""
        self.last_letter_time_s = now_ms/1000

    async def stop(self, now_ms: int) -> None:
        self.sound_manager.play_game_over()
        logger.info("GAME OVER")
        for rack in self.racks:
            rack.stop()
        self.input_devices = []
        self.running = False
        now_s = now_ms / 1000
        self.stop_time_s = now_s
        self.duration_log_f.write(
            f"{self.scores[0].score},{now_s-self.start_time_s}\n")
        self.duration_log_f.flush()
        await self._app.stop(now_ms)
        logger.info("GAME OVER OVER")

    async def next_tile(self, next_letter: str, now_ms: int) -> None:
        if self.letter.get_screen_bottom_y() + Letter.Y_INCREMENT*3 > self.rack_metrics.get_rect().y:
            next_letter = "!"
        self.letter.change_letter(next_letter, now_ms)

    def resize_previous_guesses(self, now_ms: int) -> None:
        font_size = (cast(float, self.previous_guesses_display.font.size)*4.0)/5.0
        self.previous_guesses_display = PreviousGuessesDisplay.from_instance(
            self.previous_guesses_display, max(1, int(font_size)), now_ms)
        self.remaining_previous_guesses_display = RemainingPreviousGuessesDisplay.from_instance(
            self.remaining_previous_guesses_display, int(font_size - FONT_SIZE_DELTA))
        self.previous_guesses_display.draw()
        self.remaining_previous_guesses_display.draw()

    def exec_with_resize(self, f, now_ms: int):
        retry_count = 0
        while True:
            try:
                retry_count += 1
                if retry_count > 2:
                    raise Exception("too many TextRectException")
                return f()
            except textrect.TextRectException as e:
                # print(f"resize_previous_guesses: {e}")
                self.resize_previous_guesses(now_ms)

    async def add_guess(self, previous_guesses: list[str], guess: str, player: int, now_ms: int) -> None:
        self.guess_to_player[guess] = player
        self.exec_with_resize(lambda: self.previous_guesses_display.add_guess(
            previous_guesses, guess, player, now_ms),
                              now_ms)

    async def update_previous_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        self.exec_with_resize(
            lambda: self.previous_guesses_display.update_previous_guesses(
                previous_guesses, now_ms),
            now_ms)

    async def update_remaining_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        self.exec_with_resize(
            lambda: self.remaining_previous_guesses_display.update_remaining_guesses(previous_guesses),
            now_ms)

    def update_previous_guesses_with_resizing(self, window: pygame.Surface, now_ms: int) -> None:
        def update_all_previous_guesses(self, window: pygame.Surface) -> None:
            self.previous_guesses_display.update(window, now_ms)
            self.remaining_previous_guesses_display.update(
                window, self.previous_guesses_display.surface.get_bounding_rect().height)

        self.exec_with_resize(lambda: update_all_previous_guesses(self, window),
                              now_ms)

    async def update(self, window: pygame.Surface, now_ms: int) -> None:
        incidents = []
        window.set_alpha(255)
        self.update_previous_guesses_with_resizing(window, now_ms)
        if incident := self.letter_source.update(window, now_ms):
            incidents.extend(incident)

        if self.running:
            if incident := self.letter.update(window, now_ms):
                incidents.extend(incident)

            if self.letter.locked_on or self.last_lock:
                self.last_lock = self.letter.locked_on
                if await self._app.letter_lock(self.letter.letter_index(), self.letter.locked_on, now_ms):
                    incidents.append("letter_lock")

        for player in range(self._app.player_count):
            self.racks[player].update(window, now_ms)
        for shield in self.shields:
            shield.update(window, now_ms)
            if shield.rect.y <= self.letter.get_screen_bottom_y():
                incidents.append("shield_letter_collision")
                shield.letter_collision()
                self.letter.shield_collision(now_ms)
                self.scores[shield.player].update_score(shield.score)
                self._app.add_guess(shield.letters, shield.player)
                self.sound_manager.play_crash()

        self.shields[:] = [s for s in self.shields if s.active]
        for player in range(self._app.player_count):
            self.scores[player].update(window)

        # letter collide with rack
        if self.running and self.letter.get_screen_bottom_y() > self.rack_metrics.get_rect().y:
            incidents.append("letter_rack_collision")
            if self.letter.letter == "!":
                await self.stop(now_ms)
            else:
                self.sound_manager.play_chunk()
                self.letter.new_fall(now_ms)
                await self.accept_letter(now_ms)
        return incidents

class BlockWordsPygame:
    def __init__(self, replay_file: str) -> None:
        self._window = pygame.display.set_mode(
            (SCREEN_WIDTH*SCALING_FACTOR, SCREEN_HEIGHT*SCALING_FACTOR))
        self.letter_font = pygame.freetype.SysFont(FONT, RackMetrics.LETTER_SIZE)
        self.the_app = None
        self.game = None
        self.replay_file = replay_file
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
            events.trigger("game.abort")
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
            pygame.mixer.Sound.play(self.add_sound)
        else:
            # Remove letter at cursor position from the guess
            if input_device.reversed:
                letter_to_remove = len(input_device.current_guess) - rack_position
                input_device.current_guess = input_device.current_guess[:letter_to_remove-1] + input_device.current_guess[letter_to_remove:]
            else:
                letter_to_remove = rack_position
                input_device.current_guess = input_device.current_guess[:letter_to_remove] + input_device.current_guess[letter_to_remove + 1:]
            if rack.select_count > 0:
                pygame.mixer.Sound.play(self.erase_sound)
        rack.select_count = len(input_device.current_guess)
        if rack.select_count == 0:
            pygame.mixer.Sound.play(self.cleared_sound)
        await self.the_app.guess_word_keyboard(input_device.current_guess, input_device.player_number, now_ms)

    async def handle_insert_action(self, input_device: InputDevice, now_ms: int):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]            
        if input_device.reversed != (rack.cursor_position >= len(input_device.current_guess)):
            # Insert letter at cursor position into the guess
            letter_at_cursor = rack.letters()[rack.cursor_position]
            input_device.current_guess += letter_at_cursor
            pygame.mixer.Sound.play(self.add_sound)
        await self.the_app.guess_word_keyboard(input_device.current_guess, input_device.player_number, now_ms)
    
    async def handle_delete_action(self, input_device: InputDevice, now_ms: int):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]
        if input_device.reversed != (rack.cursor_position < len(input_device.current_guess)):
            # Remove letter at cursor position from the guess
            input_device.current_guess = input_device.current_guess[:rack.cursor_position] + input_device.current_guess[rack.cursor_position + 1:]
            if rack.select_count > 0:
                pygame.mixer.Sound.play(self.erase_sound)
        rack.select_count = len(input_device.current_guess)
        if rack.select_count == 0:
            pygame.mixer.Sound.play(self.cleared_sound)
        await self.the_app.guess_word_keyboard(input_device.current_guess, input_device.player_number)
    
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
            pygame.mixer.Sound.play(self.left_sound)
    
    def handle_right_movement(self, input_device: InputDevice):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]
        if rack.cursor_position < tiles.MAX_LETTERS - 1:
            rack.cursor_position += 1
            rack.draw()
            pygame.mixer.Sound.play(self.right_sound)
    
    def handle_return_action(self, input_device: InputDevice):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]
        input_device.current_guess = ""
        rack.cursor_position = 0 if not input_device.reversed else 5
        rack.select_count = len(input_device.current_guess)
        pygame.mixer.Sound.play(self.cleared_sound)
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
            for player in range(MAX_PLAYERS):
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

    async def main(self, the_app: app.App, subscribe_client: aiomqtt.Client, start: bool, 
                   keyboard_player_number: int, publish_queue: asyncio.Queue, 
                   game_logger, output_logger) -> None:
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

        joysticks = []
        keyboard_input = KeyboardInput(handlers)
        input_devices = [keyboard_input]
        print(f"joystick count: {pygame.joystick.get_count()}")
        if self.replay_file:
            input_devices.append(GamepadInput(handlers))
        elif pygame.joystick.get_count() > 0:
            for j in range(pygame.joystick.get_count()):
                joysticks.append(pygame.joystick.Joystick(j))
                name = joysticks[j].get_name()
                print(f"Game controller connected: {name}")
                input_device = JOYSTICK_NAMES_TO_INPUTS[name](handlers)
                input_device.id = j
                input_devices.append(input_device)
        self.add_sound = pygame.mixer.Sound("sounds/add.wav")
        self.erase_sound = pygame.mixer.Sound("sounds/erase.wav")
        self.cleared_sound = pygame.mixer.Sound("sounds/cleared.wav")
        self.left_sound = pygame.mixer.Sound("sounds/left.wav")
        self.right_sound = pygame.mixer.Sound("sounds/right.wav")
        
        self.left_sound.set_volume(0.5)
        self.right_sound.set_volume(0.5)

        # Create dependencies for injection
        sound_manager = SoundManager()
        rack_metrics = RackMetrics()
        
        self.game = Game(the_app, self.letter_font, game_logger, output_logger, sound_manager, rack_metrics)
        
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
            mqtt_task = asyncio.create_task(self._process_mqtt_messages(
                mqtt_client, mqtt_message_queue, publish_queue), name="mqtt processor")

        time_offset = 0  # so that time doesn't go backwards after playing a replay file
        while True:
            now_ms = pygame.time.get_ticks() + time_offset

            if self.game.aborted:
                await events.stop()
                return
            
            pygame_events = self._get_pygame_events()
            events_to_log = {}
            if pygame_events:
                events_to_log['pygame'] = pygame_events

            if mqtt_events := self._get_mqtt_events(mqtt_message_queue):
                events_to_log['mqtt'] = mqtt_events

            if self.replayer.events:
                now_ms = time_offset = self._get_replay_events(pygame_events, mqtt_events)

            if await self._handle_pygame_events(pygame_events, keyboard_input, input_devices, now_ms, events_to_log):
                return
            
            for mqtt_event in mqtt_events:
                await self.handle_mqtt_message(mqtt_event['topic'], mqtt_event['payload'], now_ms)
            
            # Check if ABC start sequence should be activated
            await cubes_to_game.activate_abc_start_if_ready(publish_queue, now_ms)
            
            # Check if any ABC countdown has completed
            countdown_incidents = await cubes_to_game.abc_manager.check_countdown_completion(publish_queue, now_ms, self.game.sound_manager)
            
            screen.fill((0, 0, 0))
            # print(f"UPDATING {now_ms}")
            
            # Collect incidents from game update
            game_incidents = await self.game.update(screen, now_ms)
            
            # Combine countdown incidents with game incidents
            all_incidents = countdown_incidents + game_incidents
            
            if len(all_incidents) > 0:
                events_to_log['incidents'] = all_incidents
                # print(f"{now_ms} incidents {all_incidents}")

            if mqtt_events or pygame_events or all_incidents:
                self.game.game_logger.log_events(now_ms, events_to_log)
                
            hub75.update(screen)
            pygame.transform.scale(screen, self._window.get_rect().size, dest_surface=self._window)
            pygame.display.flip()

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
            events.trigger("game.abort")
            raise e
