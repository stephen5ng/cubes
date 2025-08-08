# From https://python-forum.io/thread-23029.html

import hub75
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
import textrect
from typing import cast
import functools

class EventType(Enum):
    PYGAME = "pygame"
    MQTT = "mqtt"

import app
from config import MAX_PLAYERS
import cubes_to_game
from mock_mqtt_client import MockMqttClient
from pygame.image import tobytes as image_to_string
from pygameasync import Clock, events
import tiles
from src.systems.sound_manager import SoundManager
from src.input.input_devices import (
    InputDevice, CubesInput, KeyboardInput, GamepadInput, DDRInput, 
    JOYSTICK_NAMES_TO_INPUTS
)
from src.rendering.metrics import RackMetrics
from src.ui.display_components import (
    LastGuessFader, FaderManager, PreviousGuessesDisplayBase,
    PreviousGuessesDisplay, RemainingPreviousGuessesDisplay
)
from src.rendering.animations import get_alpha, LetterSource
from src.game.components import Score, Shield

logger = logging.getLogger(__name__)

SCREEN_WIDTH = 192
SCREEN_HEIGHT = 256
SCALING_FACTOR = 3

TICKS_PER_SECOND = 45

FONT = "Courier"
ANTIALIAS = 1

FREE_SCORE = 0

# Global reference to letter beeps - populated by SoundManager
letter_beeps: list = []

BAD_GUESS_COLOR=Color("red")
GOOD_GUESS_COLOR=Color("Green")
OLD_GUESS_COLOR=Color("yellow")
LETTER_SOURCE_COLOR=Color("Red")

RACK_COLOR=Color("LightGrey")
SHIELD_COLOR_P0=Color("DarkOrange4")
SHIELD_COLOR_P1=Color("DarkSlateBlue")
SCORE_COLOR=Color("White")
FADER_COLOR_P0=Color("orange")
FADER_COLOR_P1=Color("lightblue")
REMAINING_PREVIOUS_GUESSES_COLOR = Color("grey")
PREVIOUS_GUESSES_COLOR = Color("orange")

FONT_SIZE_DELTA = 4

# Player colors for shields and faders
PLAYER_COLORS = [SHIELD_COLOR_P0, SHIELD_COLOR_P1]
FADER_PLAYER_COLORS = [FADER_COLOR_P0, FADER_COLOR_P1]

class GameReplayer:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.events = []
        
    def load_events(self):
        if not self.log_file:
            return
            
        with open(self.log_file, 'r') as f:
            lines = f.readlines()

        if lines and lines[0].startswith('{"event_type": "seed"'):
            lines = lines[1:]

        for line in lines:
            if line.strip():
                event = json.loads(line)
                self.events.append(event)
        
        self.events.reverse()


# get_alpha function moved to src/rendering/animations.py

class GuessType(Enum):
    BAD = 0
    OLD = 1
    GOOD = 2

# Input device classes moved to src/input/input_devices.py
# RackMetrics class moved to src/rendering/metrics.py

class Letter:
    DROP_TIME_MS = 15000
    NEXT_COLUMN_MS = 1000
    ANTIALIAS = 1
    ROUNDS = 15
    Y_INCREMENT = SCREEN_HEIGHT // ROUNDS
    COLUMN_SHIFT_INTERVAL_MS = 10000

    def __init__(
        self, font: pygame.freetype.Font, initial_y: int, rack_metrics: RackMetrics, output_logger) -> None:
        self.rack_metrics = rack_metrics
        self.game_area_offset_y = initial_y  # Offset from screen top to game area
        self.font = font
        self.letter_width, self.letter_height = rack_metrics.letter_width, rack_metrics.letter_height
        self.width = rack_metrics.letter_width
        self.height = SCREEN_HEIGHT - (rack_metrics.letter_height + initial_y)
        self.fraction_complete = 0.0
        self.locked_on = False
        self.start_x = self.rack_metrics.get_rect().x
        self.bounce_sound = pygame.mixer.Sound("sounds/bounce.wav")
        self.bounce_sound.set_volume(0.1)
        self.next_letter_easing = easing_functions.ExponentialEaseOut(start=0, end=1, duration=1)
        self.left_right_easing = easing_functions.ExponentialEaseIn(start=1000, end=10000, duration=1)
        self.top_bottom_easing = easing_functions.CubicEaseIn(start=0, end=1, duration=1)
        self.output_logger = output_logger

        self.start(0)
        self.draw(0)

    def start(self, now_ms: int) -> None:
        self.letter = ""
        self.letter_ix = 1
        self.start_fall_y = 0
        self.current_fall_start_y = 0
        self.column_move_direction = 1
        self.next_column_move_time_ms = now_ms + self.NEXT_COLUMN_MS
        self.fall_duration_ms = self.DROP_TIME_MS
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.pos = [0, 0]
        self.start_fall_time_ms = now_ms
        self.last_beep_time_ms = now_ms

    def stop(self) -> None:
        self.letter = ""

    def letter_index(self) -> int:
        if self.fraction_complete_eased >= 0.5:
            return self.letter_ix
        return self.letter_ix - self.column_move_direction

    def get_screen_bottom_y(self) -> int:
        return self.game_area_offset_y + self.pos[1] + self.letter_height

    def _update_beeping(self, now_ms: int) -> None:
        distance_from_top = self.pos[1] / SCREEN_HEIGHT
        distance_from_bottom = 1 - distance_from_top
        if now_ms > self.last_beep_time_ms + (distance_from_bottom*distance_from_bottom)*7000:
            letter_beeps_ix = min(len(letter_beeps)-1, int(10*distance_from_top))
            pygame.mixer.Sound.play(letter_beeps[letter_beeps_ix])
            self.last_beep_time_ms = now_ms

    def _update_column_movement(self, now_ms: int) -> list[str]:
        incidents = []
        if now_ms > self.next_column_move_time_ms:
            incidents.append("letter_column_move")
            if not self.locked_on:
                self.letter_ix = self.letter_ix + self.column_move_direction
                if self.letter_ix < 0 or self.letter_ix >= tiles.MAX_LETTERS:
                    self.column_move_direction *= -1
                    self.letter_ix = self.letter_ix + self.column_move_direction*2

                self.next_column_move_time_ms = now_ms + self.NEXT_COLUMN_MS
                pygame.mixer.Sound.play(self.bounce_sound)
            
            self.output_logger.log_letter_position_change(self.pos[0], self.pos[1], now_ms)
        return incidents

    def _calculate_position(self, now_ms: int) -> None:
        remaining_ms = min(max(0, self.next_column_move_time_ms - now_ms), self.NEXT_COLUMN_MS)
        self.fraction_complete = 1.0 - remaining_ms/self.NEXT_COLUMN_MS
        self.fraction_complete_eased = self.next_letter_easing(self.fraction_complete)
        boost_x = 0 if self.locked_on else int(self.column_move_direction*(self.width*(self.fraction_complete_eased - 1)))
        self.pos[0] = self.rack_metrics.get_rect().x + self.rack_metrics.get_letter_rect(self.letter_ix, self.letter).x + boost_x

    def _update_locked_state(self) -> None:
        self.locked_on = (self.fraction_complete_eased >= 1) and (self.get_screen_bottom_y() + Letter.Y_INCREMENT*2 > self.height)

    def draw(self, now_ms) -> None:
        self.surface = self.font.render(self.letter, LETTER_SOURCE_COLOR)[0]
        self._calculate_position(now_ms)
        self._update_locked_state()

    def update(self, window: pygame.Surface, now_ms: int) -> None:
        incidents = []
        fall_percent = (now_ms - self.start_fall_time_ms)/self.fall_duration_ms
        fall_easing = self.top_bottom_easing(fall_percent)
        self.pos[1] = int(self.current_fall_start_y + fall_easing * self.height)
        
        self._update_beeping(now_ms)
        self.draw(now_ms)

        screen_pos = self.pos.copy()
        screen_pos[1] += self.game_area_offset_y
        window.blit(self.surface, screen_pos)
        
        incidents.extend(self._update_column_movement(now_ms))
        return incidents

    def shield_collision(self, now_ms: int) -> None:
        # logger.debug(f"---------- {self.start_fall_y}, {self.pos[1]}, {new_pos}, {self.pos[1] - new_pos}")
        self.pos[1] = int(self.start_fall_y + (self.pos[1] - self.start_fall_y)/2)
        self.current_fall_start_y = int(self.start_fall_y + (self.pos[1] - self.start_fall_y)/2)
        self.start_fall_time_ms = now_ms

    def change_letter(self, new_letter: str, now_ms: int) -> None:
        self.letter = new_letter
        self.draw(now_ms)

    def new_fall(self, now_ms: int) -> None:
        self.start_fall_y += Letter.Y_INCREMENT
        self.fall_duration_ms = self.DROP_TIME_MS * (self.height - self.start_fall_y) / self.height
        self.pos[1] = self.current_fall_start_y = self.start_fall_y
        self.start_fall_time_ms = now_ms

class Rack:
    LETTER_TRANSITION_DURATION_MS = 4000
    GUESS_TRANSITION_DURATION_MS = 800

    def __init__(self, the_app: app.App, rack_metrics: RackMetrics, falling_letter: Letter, player: int) -> None:
        self.the_app = the_app
        self.rack_metrics = rack_metrics
        self.player = player
        self.font = rack_metrics.font
        self.falling_letter = falling_letter
        self.tiles: list[tiles.Tile] = []
        self.running = False
        self.border = " "
        self.last_update_letter_ms = -Rack.LETTER_TRANSITION_DURATION_MS
        self.easing = easing_functions.QuinticEaseInOut(start=0, end=255, duration=1)
        self.last_guess_ms = -Rack.GUESS_TRANSITION_DURATION_MS
        self.highlight_length = 0
        self.select_count = 0
        self.cursor_position = 0
        self.transition_tile: tiles.Tile = None
        self.guess_type = GuessType.BAD
        self.guess_type_to_rect_color = {
            GuessType.BAD: BAD_GUESS_COLOR,
            GuessType.OLD: OLD_GUESS_COLOR,
            GuessType.GOOD: GOOD_GUESS_COLOR
            }
        self.game_over_surface, game_over_rect = self.font.render("GAME OVER", RACK_COLOR)
        self.game_over_pos = [SCREEN_WIDTH/2 - game_over_rect.width/2, rack_metrics.y]
        
        # Player -1 means single-player mode.
        self.left_offset_by_player = [0, -self.rack_metrics.letter_width*3, self.rack_metrics.letter_width*3]
        self.rack_color_by_player = [FADER_COLOR_P0, FADER_COLOR_P0, FADER_COLOR_P1]

    def _render_letter(self, surface: pygame.Surface,
        position: int, letter: str, color: pygame.Color) -> None:
        self.font.render_to(surface,
            self.rack_metrics.get_letter_rect(position, letter), letter, color)

    def letters(self) -> str:
        return ''.join([l.letter for l in self.tiles])

    def draw(self) -> None:
        self.surface = pygame.Surface(self.rack_metrics.get_size())
        if self.letters():
            pygame.draw.rect(self.surface, Color("grey"), 
                             self.rack_metrics.get_largest_letter_rect(self.cursor_position))
        for ix, letter in enumerate(self.letters()):
            self._render_letter(self.surface, ix, letter, self.rack_color_by_player[self.player+1])
            
        pygame.draw.rect(self.surface,
            self.guess_type_to_rect_color[self.guess_type],
            self.rack_metrics.get_select_rect(self.select_count, self.player),
            1)

    def start(self) -> None:
        self.running = True
        self.draw()

    def stop(self) -> None:
        self.running = False
        self.draw()

    async def update_rack(self, 
                          tiles: list[tiles.Tile], 
                          highlight_length: int, 
                          guess_length: int,
                          now_ms: int) -> None:
        self.tiles = tiles
        self.highlight_length = highlight_length
        self.last_guess_ms = now_ms
        self.select_count = guess_length
        self.draw()

    async def update_letter(self, tile: tiles.Tile, now_ms: int) -> None:
        self.last_update_letter_ms = now_ms
        self.transition_tile = tile
        self.draw()

    def _render_fading_letters(self, surface_with_faders: pygame.Surface, now: int) -> None:
        def make_color(color: pygame.Color, alpha: int) -> pygame.Color:
            new_color = Color(color)
            new_color.a = alpha
            return new_color

        new_letter_alpha = get_alpha(self.easing,
            self.last_update_letter_ms, Rack.LETTER_TRANSITION_DURATION_MS, now)
        if new_letter_alpha and self.transition_tile in self.tiles:
            self._render_letter(
                surface_with_faders,
                self.tiles.index(self.transition_tile),
                self.transition_tile.letter,
                make_color(LETTER_SOURCE_COLOR, new_letter_alpha))

        good_word_alpha = get_alpha(self.easing, self.last_guess_ms, Rack.GUESS_TRANSITION_DURATION_MS, now)
        if good_word_alpha:
            color = make_color(GOOD_GUESS_COLOR, good_word_alpha)
            letters = self.letters()
            for ix in range(0, self.highlight_length):
                self._render_letter(surface_with_faders, ix, letters[ix], color)

    def _render_flashing_letters(self, surface_with_faders: pygame.Surface) -> None:
        if self.falling_letter.locked_on and self.running:
            if random.randint(0, 2) == 0:
                if self.falling_letter.letter == "!":
                    letter_index = random.randint(0, 6)
                else:
                    letter_index = self.falling_letter.letter_index()
                    if self.the_app.player_count > 1:
                        # Only flash letters in our half of the rack
                        hit_rack = 0 if letter_index < 3 else 1
                        if self.player != hit_rack:
                            return
                        letter_index += 3 * (1 if hit_rack == 0 else -1)
                surface_with_faders.fill(Color("black"),
                    rect=self.rack_metrics.get_largest_letter_rect(letter_index),
                    special_flags=pygame.BLEND_RGBA_MULT)

    def update(self, window: pygame.Surface, now: int) -> None:
        if not self.running:
            window.blit(self.game_over_surface, self.game_over_pos)
            return
        surface = self.surface.copy()
        self._render_flashing_letters(surface)
        self._render_fading_letters(surface, now)
        top_left = self.rack_metrics.get_rect().topleft
        player_index = 0 if self.the_app.player_count == 1 else self.player+1
        top_left = (top_left[0] + self.left_offset_by_player[player_index], top_left[1])
        window.blit(surface, top_left)

# Shield class moved to src/game/components.py

# Score class moved to src/game/components.py

class LastGuessFader:
    FADE_DURATION_MS = 2000

    def __init__(self, last_update_ms: int, duration: int, surface: pygame.Surface, position: tuple[int, int]) -> None:
        self.last_update_ms = last_update_ms
        self.duration = duration
        self.easing = easing_functions.QuinticEaseInOut(start=0, end = 255, duration = 1)
        self.last_guess = ""
        self.last_guess_surface = surface
        self.last_guess_position = position
        self.alpha = 1

    def blit(self, target: pygame.Surface, now: int) -> None:
        self.alpha = get_alpha(self.easing, self.last_update_ms, self.duration, now)
        if self.alpha:
            self.last_guess_surface.set_alpha(self.alpha)
            target.blit(self.last_guess_surface, self.last_guess_position)

class FaderManager:
    def __init__(self, previous_guesses: list[str], font: pygame.freetype.Font, text_rect_renderer: textrect.TextRectRenderer):
        self._previous_guesses = previous_guesses
        self._text_rect_renderer = text_rect_renderer
        self._font = font
        
    @staticmethod
    @functools.lru_cache(maxsize=64)
    def _cached_render(font: pygame.freetype.Font, text: str, color_rgb: tuple[int, int, int]) -> pygame.Surface:
        return font.render(text, pygame.Color(*color_rgb))[0]

    def create_fader(self, last_guess: str, last_update_ms: int, duration: int, color: pygame.Color) -> LastGuessFader:
        last_guess_surface = self._cached_render(self._font, last_guess, (color.r, color.g, color.b))
        last_guess_position = self._text_rect_renderer.get_pos(last_guess)
        return LastGuessFader(last_update_ms, duration, last_guess_surface, last_guess_position)
class PreviousGuessesDisplayBase:
    FONT = "Arial"

    def __init__(self, font_size: int) -> None:
        self.font = pygame.freetype.SysFont(PreviousGuessesDisplayBase.FONT, font_size)
        self.font.kerning = True
        self._text_rect_renderer = textrect.TextRectRenderer(self.font,
                pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

class PreviousGuessesDisplay(PreviousGuessesDisplayBase):
    FONT_SIZE = 30
    POSITION_TOP = 24
    FADE_DURATION_NEW_GUESS = 2000
    FADE_DURATION_OLD_GUESS = 500
    PLAYER_COLORS = [SHIELD_COLOR_P0, SHIELD_COLOR_P1]  # Static array for player colors
    FADER_PLAYER_COLORS = [FADER_COLOR_P0, FADER_COLOR_P1]

    def __init__(self, font_size: int, guess_to_player: dict[str, int]) -> None:
        super().__init__(font_size)
        self.fader_inputs = []
        self.previous_guesses = []
        self.bloop_sound = pygame.mixer.Sound("./sounds/bloop.wav")
        self.bloop_sound.set_volume(0.2)
        self.guess_to_player = guess_to_player
        self.fader_manager = FaderManager(self.previous_guesses, self.font, self._text_rect_renderer)
        self.faders: list[LastGuessFader] = []
        self.draw()

    @classmethod
    def from_instance(cls, instance: 'PreviousGuessesDisplay', font_size: int, now_ms: int) -> 'PreviousGuessesDisplay':
        """Create a new instance from an existing one with a new font size."""
        new_instance = cls(font_size, instance.guess_to_player)
        new_instance.previous_guesses = instance.previous_guesses
        new_instance.fader_inputs = instance.fader_inputs
        new_instance.bloop_sound = instance.bloop_sound
        if instance.previous_guesses and instance.fader_inputs:
            new_instance._recreate_faders(now_ms)
        return new_instance

    def _try_add_fader(self, guess: str, color: pygame.Color, duration: int, now_ms: int) -> None:
        """Try to add a fader for the given guess if it exists in previous_guesses."""
        if guess in self.previous_guesses:
            fader = self.fader_manager.create_fader(guess, now_ms, duration, color)
            self.faders.append(fader)

    def _recreate_faders(self, now_ms: int) -> None:
        self.faders = []
        for last_guess, last_update_ms, color, duration in self.fader_inputs:
            self._try_add_fader(last_guess, color, duration, now_ms)

    def draw(self) -> None:
        self.surface = self._text_rect_renderer.render(
            self.previous_guesses,
            [self.PLAYER_COLORS[self.guess_to_player.get(guess, 0)] for guess in self.previous_guesses])

    def old_guess(self, old_guess: str, now_ms: int) -> None:
        self.fader_inputs.append(
            [old_guess, now_ms, OLD_GUESS_COLOR, PreviousGuessesDisplay.FADE_DURATION_OLD_GUESS])
        self._try_add_fader(old_guess,
                            OLD_GUESS_COLOR,
                            PreviousGuessesDisplay.FADE_DURATION_OLD_GUESS,
                            now_ms)
        self.draw()
        pygame.mixer.Sound.play(self.bloop_sound)

    def add_guess(self, previous_guesses: list[str], guess: str, player: int, now_ms: int) -> None:
        self.fader_inputs.append(
            [guess, now_ms, self.FADER_PLAYER_COLORS[player], PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS])
        self.update_previous_guesses(previous_guesses, now_ms)
        self._try_add_fader(guess, 
                            self.FADER_PLAYER_COLORS[player],
                            PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS,
                            now_ms)

    def update_previous_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        self.previous_guesses = previous_guesses
        self._text_rect_renderer.update_pos_dict(self.previous_guesses)
        self.fader_manager = FaderManager(self.previous_guesses, self.font, self._text_rect_renderer)        
        self._recreate_faders(now_ms)
        self.draw()

    def update(self, window: pygame.Surface, now: int) -> None:
        surface_with_faders = self.surface.copy()
        for fader in self.faders:
            fader.blit(surface_with_faders, now)

        # remove finished faders
        self.faders[:] = [f for f in self.faders if f.alpha]

        # remove finished faders from fader_inputs
        fader_guesses = [f.last_guess for f in self.faders]
        self.fader_inputs = [f for f in self.fader_inputs if f[0] in fader_guesses]

        window.blit(surface_with_faders, [0, PreviousGuessesDisplay.POSITION_TOP])

class RemainingPreviousGuessesDisplay(PreviousGuessesDisplayBase):
    COLOR = Color("grey")
    TOP_GAP = 3
    PLAYER_COLORS = [pygame.Color(SHIELD_COLOR_P0.r, SHIELD_COLOR_P0.g, SHIELD_COLOR_P0.b, 192),
                     pygame.Color(SHIELD_COLOR_P1.r, SHIELD_COLOR_P1.g, SHIELD_COLOR_P1.b, 192)]  # Static array for player colors with 0.5 alpha

    def __init__(self, font_size: int, guess_to_player: dict[str, int]) -> None:
        super().__init__(font_size)
        self.guess_to_player = guess_to_player
        self.color = REMAINING_PREVIOUS_GUESSES_COLOR
        self.surface = pygame.Surface((0, 0))
        self.remaining_guesses = []

    @classmethod
    def from_instance(cls, instance: 'RemainingPreviousGuessesDisplay', font_size: int) -> 'RemainingPreviousGuessesDisplay':
        """Create a new instance from an existing one with a new font size."""
        new_instance = cls(font_size, instance.guess_to_player)
        new_instance.remaining_guesses = instance.remaining_guesses
        new_instance.color = instance.color
        return new_instance

    def update(self, window: pygame.Surface, height: int) -> None:
        top = height + PreviousGuessesDisplay.POSITION_TOP + RemainingPreviousGuessesDisplay.TOP_GAP
        total_height = top + self.surface.get_bounding_rect().height
        if total_height > SCREEN_HEIGHT:
            raise textrect.TextRectException("can't update RemainingPreviousGuessesDisplay")
        window.blit(self.surface, [0, top])

    def update_remaining_guesses(self, remaining_guesses: list[str]) -> None:
        self.remaining_guesses = remaining_guesses
        self.draw()

    def draw(self) -> None:
        self.surface = self._text_rect_renderer.render(
            self.remaining_guesses,
            [self.PLAYER_COLORS[self.guess_to_player.get(guess, 0)] for guess in self.remaining_guesses])

# LetterSource class moved to src/rendering/animations.py

# SoundManager class moved to src/systems/sound_manager.py

class Game:
    def __init__(self, the_app: app.App, letter_font: pygame.freetype.Font, game_logger, output_logger) -> None:
        self._app = the_app
        self.scores = [Score(the_app, player) for player in range(MAX_PLAYERS)]
        letter_y = self.scores[0].get_size()[1] + 4
        self.rack_metrics = RackMetrics()
        self.game_logger = game_logger
        self.output_logger = output_logger
        self.letter = Letter(letter_font, letter_y, self.rack_metrics, self.output_logger)
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
        self.game_log_f = open("gamelog.csv", "a+")
        self.duration_log_f = open("durationlog.csv", "a+")
        self.sound_manager = SoundManager()
        # Populate global letter_beeps from sound manager
        global letter_beeps
        letter_beeps = self.sound_manager.get_letter_beeps()
        self.input_devices = []
        self.last_lock = False

        # TODO(sng): remove f
        events.on(f"game.stage_guess")(self.stage_guess)
        events.on(f"game.old_guess")(self.old_guess)
        events.on(f"game.bad_guess")(self.bad_guess)
        events.on(f"game.next_tile")(self.next_tile)
        events.on(f"game.abort")(self.abort)
        events.on(f"game.start")(self.start_cubes)
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
        print(f"start_cubes {now_ms}")
        await self.start(CubesInput(None), now_ms)

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
                letter_index = self.letter.letter_index() if self.letter.locked_on else None
                incidents.append("letter_lock")
                if await self._app.letter_lock(letter_index, now_ms):
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
            await self.game.start_cubes(now_ms)
            # events.trigger("game.start", now_ms)
        elif topic_str == "app/abort":
            events.trigger("game.abort")
        elif topic_str == "game/guess":
            payload_str = payload.decode() if payload else ""
            await self.the_app.guess_word_keyboard(payload_str, 1, now_ms)
        elif topic_str.startswith("cube/nfc/"):
            # Handle None payload by converting to empty string
            # payload_data = payload.decode() if payload is not None else ""
            # Create a simple message-like object for cubes_to_game
            message = type('Message', (), {
                'topic': type('Topic', (), {'value': topic_str})(),
                'payload': payload.encode() if payload is not None else b''
            })()
            # print(f"!!!-----> message: {message}")
            await cubes_to_game.handle_mqtt_message(self._publish_queue, message, now_ms)

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
        print(f"start_game {input_device} {now_ms}")
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
            # print(f"Replay mode: loaded {len(self.replayer.events)} events from {self.replay_file}")
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

        self.game = Game(the_app, self.letter_font, game_logger, output_logger)
        
        self.game.game_logger.start_logging()
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
            
            screen.fill((0, 0, 0))
            # print(f"UPDATING {now_ms}")
            if len(incidents := await self.game.update(screen, now_ms)) > 0:
                events_to_log['incidents'] = incidents
                # print(f"{now_ms} incidents {incidents}")

            if mqtt_events or pygame_events or incidents:
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
