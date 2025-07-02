# From https://python-forum.io/thread-23029.html

import hub75
import aiofiles
import aiomqtt
import argparse
import asyncio
from datetime import datetime
import easing_functions
from enum import Enum
import logging
import math
import pygame
import pygame.freetype
from pygame import Color
import random
import textrect
from typing import cast
import functools

import app
from config import PLAYER_COUNT
from pygame.image import tobytes as image_to_string
from pygameasync import Clock, EventEngine, events
import tiles

logger = logging.getLogger(__name__)

SCREEN_WIDTH = 192
SCREEN_HEIGHT = 256
SCALING_FACTOR = 3

TICKS_PER_SECOND = 45

FONT = "Courier"
ANTIALIAS = 1

FREE_SCORE = 0

letter_beeps: list[pygame.Sound] = []

BAD_GUESS_COLOR=Color("red")
GOOD_GUESS_COLOR=Color("Green")
OLD_GUESS_COLOR=Color("darkgray")
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

def get_alpha(
    easing: easing_functions.easing.EasingBase, last_update: float, duration: float) -> int:
    remaining_ms = duration - (pygame.time.get_ticks() - last_update)
    if 0 < remaining_ms < duration:
        return int(easing(remaining_ms / duration))
    return 0

class GuessType(Enum):
    BAD = 0
    OLD = 1
    GOOD = 2

class RackMetrics():
    LETTER_SIZE = 24
    LETTER_BORDER = 0
    BOTTOM_MARGIN = 1
    def __init__(self) -> None:
        self.font = pygame.freetype.SysFont(FONT, self.LETTER_SIZE)
        self.letter_width = self.font.get_rect("A").size[0] + self.LETTER_BORDER
        self.letter_height = self.font.get_rect("S").size[1] + self.LETTER_BORDER+self.BOTTOM_MARGIN
        self.x = SCREEN_WIDTH/2 - self.letter_width*tiles.MAX_LETTERS/2
        self.y = SCREEN_HEIGHT - self.letter_height

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.x,
            self.y,
            self.letter_width*tiles.MAX_LETTERS,
            self.letter_height)

    def get_letter_rect(self, position: int, letter: str) -> pygame.Rect:
        this_letter_width = self.font.get_rect(letter).width
        this_letter_margin = (self.letter_width - this_letter_width) / 2
        x = self.letter_width*position + this_letter_margin
        y = self.LETTER_BORDER/2+self.BOTTOM_MARGIN
        return pygame.Rect(x, y, this_letter_width, self.letter_height - self.LETTER_BORDER)

    def get_largest_letter_rect(self, position: int) -> pygame.Rect:
        x = self.letter_width*position + self.LETTER_BORDER/2
        y = self.LETTER_BORDER/2
        return pygame.Rect(x, y, self.letter_width - self.LETTER_BORDER,
            self.letter_height - self.LETTER_BORDER)

    def get_size(self) -> tuple[int, int]:
        return self.get_rect().size

    def get_select_rect(self, select_count: int, player: int) -> pygame.Rect:
        if player == 1:
            # For player 1, start from right side and expand left
            x = self.letter_width * (tiles.MAX_LETTERS - select_count)
            return pygame.Rect(x, 0, self.letter_width * select_count, self.letter_height)
        else:
            # For player 0, start from left side and expand right (original behavior)
            return pygame.Rect(0, 0, self.letter_width * select_count, self.letter_height)

class Letter():
    DROP_TIME_MS = 15000
    NEXT_COLUMN_MS = 1000
    ANTIALIAS = 1
    ROUNDS = 15
    Y_INCREMENT = SCREEN_HEIGHT // ROUNDS
    COLUMN_SHIFT_INTERVAL_MS = 10000

    def __init__(
        self, font: pygame.freetype.Font, initial_y: int, rack_metrics: RackMetrics) -> None:
        self.rack_metrics = rack_metrics
        self.new_game_y = initial_y
        self.font = font
        self.letter_width, self.letter_height = rack_metrics.letter_width, rack_metrics.letter_height
        self.width = rack_metrics.letter_width
        self.height = SCREEN_HEIGHT - (rack_metrics.letter_height + initial_y)
        self.fraction_complete = 0.0
        self.locked_on = False
        self.start_x = self.rack_metrics.get_rect().x
        self.start()
        self.start_fall_time_ms = pygame.time.get_ticks()
        self.bounce_sound = pygame.mixer.Sound("sounds/bounce.wav")
        self.bounce_sound.set_volume(0.1)
        self.next_letter_easing = easing_functions.ExponentialEaseOut(start=0, end=1, duration=1)
        self.left_right_easing = easing_functions.ExponentialEaseIn(start=1000, end=10000, duration=1)
        self.top_bottom_easing = easing_functions.CubicEaseIn(start=0, end=1, duration=1)
        self.draw()

    def start(self) -> None:
        self.letter = ""
        self.letter_ix = 0
        self.start_fall_y = 0
        self.new_start_fall_y = 0
        self.column_move_direction = 1
        self.next_column_move_time_ms = pygame.time.get_ticks()
        self.top_bottom_percent = 0
        self.total_fall_time_ms = self.DROP_TIME_MS
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.pos = [0, 0]
        self.start_fall_time_ms = pygame.time.get_ticks()
        self.last_beep_time_ms = pygame.time.get_ticks()

    def stop(self) -> None:
        self.letter = ""

    def letter_index(self) -> int:
        if self.easing_complete >= 0.5:
            return self.letter_ix
        return self.letter_ix - self.column_move_direction

    def get_screen_bottom_y(self) -> int:
        return self.new_game_y + self.pos[1] + self.letter_height

    def draw(self) -> None:
        self.surface = self.font.render(self.letter, LETTER_SOURCE_COLOR)[0]
        remaining_ms = max(0, self.next_column_move_time_ms - pygame.time.get_ticks())
        self.fraction_complete = 1.0 - remaining_ms/self.NEXT_COLUMN_MS
        self.easing_complete = self.next_letter_easing(self.fraction_complete)
        boost_x = 0 if self.locked_on else int(self.column_move_direction*(self.width*self.easing_complete - self.width))
        self.pos[0] = self.rack_metrics.get_rect().x + self.rack_metrics.get_letter_rect(self.letter_ix, self.letter).x + boost_x
        if self.easing_complete >= 1:
            self.locked_on = self.get_screen_bottom_y() + Letter.Y_INCREMENT*2 > self.height
            # print(f"{self.easing_complete} {remaining_ms} {self.fraction_complete} {self.locked_on} {self.get_screen_bottom_y() + Letter.Y_INCREMENT*2} > {self.height}")

    def update(self, window: pygame.Surface) -> None:
        now_ms = pygame.time.get_ticks()
        fall_percent = (now_ms - self.start_fall_time_ms)/self.total_fall_time_ms
        fall_easing = self.top_bottom_easing(fall_percent)
        self.pos[1] = int(self.new_start_fall_y + fall_easing * self.height)
        distance_from_top = self.pos[1] / SCREEN_HEIGHT
        distance_from_bottom = 1 - distance_from_top
        if now_ms > self.last_beep_time_ms + (distance_from_bottom*distance_from_bottom)*7000:
            pygame.mixer.Sound.play(letter_beeps[int(10*distance_from_top)])
            self.last_beep_time_ms = now_ms

        self.draw()

        blit_pos = self.pos.copy()
        blit_pos[1] += self.new_game_y
        window.blit(self.surface, blit_pos)
        if now_ms > self.next_column_move_time_ms:
            if not self.locked_on:
                self.letter_ix = self.letter_ix + self.column_move_direction
                if self.letter_ix < 0 or self.letter_ix >= tiles.MAX_LETTERS:
                    self.column_move_direction *= -1
                    self.letter_ix = self.letter_ix + self.column_move_direction*2

                self.next_column_move_time_ms = now_ms + self.NEXT_COLUMN_MS
                pygame.mixer.Sound.play(self.bounce_sound)

    def shield_collision(self) -> None:
        # logger.debug(f"---------- {self.start_fall_y}, {self.pos[1]}, {new_pos}, {self.pos[1] - new_pos}")
        self.pos[1] = int(self.start_fall_y + (self.pos[1] - self.start_fall_y)/2)
        self.new_start_fall_y = int(self.start_fall_y + (self.pos[1] - self.start_fall_y)/2)
        self.start_fall_time_ms = pygame.time.get_ticks()

    def change_letter(self, new_letter: str) -> None:
        self.letter = new_letter
        self.draw()

    def new_fall(self) -> None:
        self.start_fall_y += Letter.Y_INCREMENT
        self.total_fall_time = self.DROP_TIME_MS * (self.height - self.start_fall_y) / self.height
        self.pos[1] = self.new_start_fall_y = self.start_fall_y
        self.start_fall_time_ms = pygame.time.get_ticks()

class Rack():
    LETTER_TRANSITION_DURATION_MS = 4000
    GUESS_TRANSITION_DURATION_MS = 800

    def __init__(self, rack_metrics: RackMetrics, falling_letter: Letter, player: int) -> None:
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
        self.surface.fill(Color("black"))
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

    async def update_rack(self, tiles: list[tiles.Tile], highlight_length: int, guess_length: int) -> None:
        self.tiles = tiles
        self.highlight_length = highlight_length
        self.last_guess_ms = pygame.time.get_ticks()
        self.select_count = guess_length
        self.draw()

    async def update_letter(self, tile: tiles.Tile) -> None:
        self.last_update_letter_ms = pygame.time.get_ticks()
        self.transition_tile = tile
        self.draw()

    def _render_fading_letters(self, surface_with_faders: pygame.Surface) -> None:
        def make_color(color: pygame.Color, alpha: int) -> pygame.Color:
            new_color = Color(color)
            new_color.a = alpha
            return new_color

        new_letter_alpha = get_alpha(self.easing,
            self.last_update_letter_ms, Rack.LETTER_TRANSITION_DURATION_MS)
        if new_letter_alpha and self.transition_tile in self.tiles:
            self._render_letter(
                surface_with_faders,
                self.tiles.index(self.transition_tile),
                self.transition_tile.letter,
                make_color(LETTER_SOURCE_COLOR, new_letter_alpha))

        good_word_alpha = get_alpha(self.easing, self.last_guess_ms, Rack.GUESS_TRANSITION_DURATION_MS)
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
                    if PLAYER_COUNT > 1:
                        # Only flash letters in our half of the rack
                        hit_rack = 0 if letter_index < 3 else 1
                        if self.player != hit_rack:
                            return
                        letter_index += 3 * (1 if hit_rack == 0 else -1)
                surface_with_faders.fill(Color("black"),
                    rect=self.rack_metrics.get_largest_letter_rect(letter_index),
                    special_flags=pygame.BLEND_RGBA_MULT)

    def update(self, window: pygame.Surface) -> None:
        if not self.running:
            window.blit(self.game_over_surface, self.game_over_pos)
            return

        surface = self.surface.copy()
        self._render_flashing_letters(surface)
        self._render_fading_letters(surface)
        top_left = self.rack_metrics.get_rect().topleft
        top_left = (top_left[0] + self.left_offset_by_player[self.player+1], top_left[1])
        window.blit(surface, top_left)

class Shield():
    ACCELERATION = 1.05

    def __init__(self, base_pos: tuple[int, int], letters: str, score: int, player: int) -> None:
        self.font = pygame.freetype.SysFont("Arial", int(2+math.log(1+score)*8))
        self.letters = letters
        self.pos = [base_pos[0], float(base_pos[1])]
        self.pos[1] -= self.font.get_rect("A").height
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.speed = -math.log(1+score) / 10
        self.score = score
        self.active = True
        self.player = player
        self.draw()

    def draw(self) -> None:
        self.surface = self.font.render(self.letters, PreviousGuessesDisplay.FADER_PLAYER_COLORS[self.player])[0]
        self.pos[0] = int(SCREEN_WIDTH/2 - self.surface.get_width()/2)

    def update(self, window: pygame.Surface) -> None:
        if self.active:
            self.pos[1] += self.speed
            self.speed *= 1.05
            window.blit(self.surface, self.pos)

            # Get the tightest rectangle around the content for collision detection.
            self.rect = self.surface.get_bounding_rect().move(self.pos[0], self.pos[1])

    def letter_collision(self) -> None:
        self.active = False
        self.pos[1] = SCREEN_HEIGHT

class Score():
    def __init__(self, player: int) -> None:
        self.font = pygame.freetype.SysFont(FONT, RackMetrics.LETTER_SIZE)
        self.pos = [0, 0]
        if player == -1:
            self.x = SCREEN_WIDTH/2
        else:
            self.x = SCREEN_WIDTH/3 * (player+1)
        self.start()
        self.draw()

    def get_size(self) -> tuple[int, int]:
        return self.surface.get_size()

    def start(self) -> None:
        self.score = 0
        self.draw()

    def draw(self) -> None:
        self.surface = self.font.render(str(self.score), SCORE_COLOR)[0]
        self.pos[0] = int(self.x - self.surface.get_width()/2)

    def update_score(self, score: int) -> None:
        self.score += score
        self.draw()

    def update(self, window: pygame.Surface) -> None:
        window.blit(self.surface, self.pos)

class LastGuessFader():
    FADE_DURATION_MS = 2000

    def __init__(self, last_update_ms: int, duration: int, surface: pygame.Surface, position: tuple[int, int]) -> None:
        self.last_update_ms = last_update_ms
        self.duration = duration
        self.easing = easing_functions.QuinticEaseInOut(start=0, end = 255, duration = 1)
        self.last_guess = ""
        self.last_guess_surface = surface
        self.last_guess_position = position
        self.alpha = 1

    def blit(self, target) -> None:
        self.alpha = get_alpha(self.easing, self.last_update_ms, self.duration)
        if self.alpha:
            self.last_guess_surface.set_alpha(self.alpha)
            target.blit(self.last_guess_surface, self.last_guess_position)

class FaderManager():
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
class PreviousGuessesDisplayBase():
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
    def from_instance(cls, instance: 'PreviousGuessesDisplay', font_size: int) -> 'PreviousGuessesDisplay':
        """Create a new instance from an existing one with a new font size."""
        new_instance = cls(font_size, instance.guess_to_player)
        new_instance.previous_guesses = instance.previous_guesses
        new_instance.fader_inputs = instance.fader_inputs
        new_instance.bloop_sound = instance.bloop_sound
        if instance.previous_guesses and instance.fader_inputs:
            new_instance._recreate_faders()
        return new_instance

    def _try_add_fader(self, guess: str, color: pygame.Color, duration: int) -> None:
        """Try to add a fader for the given guess if it exists in previous_guesses."""
        if guess in self.previous_guesses:
            fader = self.fader_manager.create_fader(guess, pygame.time.get_ticks(), duration, color)
            self.faders.append(fader)

    def _recreate_faders(self) -> None:
        self.faders = []
        for last_guess, last_update_ms, color, duration in self.fader_inputs:
            self._try_add_fader(last_guess, color, duration)

    def draw(self) -> None:
        self.surface = self._text_rect_renderer.render(
            self.previous_guesses,
            [self.PLAYER_COLORS[self.guess_to_player.get(guess, 0)] for guess in self.previous_guesses])

    def old_guess(self, old_guess: str) -> None:
        self.fader_inputs.append(
            [old_guess, pygame.time.get_ticks(), OLD_GUESS_COLOR, PreviousGuessesDisplay.FADE_DURATION_OLD_GUESS])
        self._try_add_fader(old_guess, OLD_GUESS_COLOR, PreviousGuessesDisplay.FADE_DURATION_OLD_GUESS)
        self.draw()
        pygame.mixer.Sound.play(self.bloop_sound)

    def add_guess(self, previous_guesses: list[str], guess: str, player: int) -> None:
        self.fader_inputs.append(
            [guess, pygame.time.get_ticks(), self.FADER_PLAYER_COLORS[player], PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS])
        self.update_previous_guesses(previous_guesses)
        self._try_add_fader(guess, self.FADER_PLAYER_COLORS[player], PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS)

    def update_previous_guesses(self, previous_guesses: list[str]) -> None:
        self.previous_guesses = previous_guesses
        self._text_rect_renderer.update_pos_dict(self.previous_guesses)
        self.fader_manager = FaderManager(self.previous_guesses, self.font, self._text_rect_renderer)        
        self._recreate_faders()
        self.draw()

    def update(self, window: pygame.Surface) -> None:
        surface_with_faders = self.surface.copy()
        for fader in self.faders:
            fader.blit(surface_with_faders)

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

class LetterSource():
    ALPHA = 128
    ANIMATION_DURAION_MS = 200
    MIN_HEIGHT = 1
    MAX_HEIGHT = 20
    def __init__(self, letter: Letter, x: int, width: int, initial_y: int) -> None:
        self.x = x
        self.last_y = 0
        self.initial_y = initial_y
        self.height = LetterSource.MIN_HEIGHT
        self.width = width
        self.letter = letter
        self.easing = easing_functions.QuinticEaseInOut(start=1, end=LetterSource.MAX_HEIGHT, duration=1)
        self.draw()

    def draw(self) -> None:
        self.surface = pygame.Surface([self.width, self.height], pygame.SRCALPHA)
        self.surface.set_alpha(LetterSource.ALPHA)
        self.surface.fill(LETTER_SOURCE_COLOR)

    def update(self, window: pygame.Surface) -> None:
        if self.last_y != self.letter.start_fall_y:
            self.last_update = pygame.time.get_ticks()
            self.height = LetterSource.MAX_HEIGHT
            self.last_y = self.letter.start_fall_y
            self.draw()
        elif self.height > LetterSource.MIN_HEIGHT:
            self.height = get_alpha(self.easing, self.last_update, LetterSource.ANIMATION_DURAION_MS)
            self.draw()
        self.pos = [self.x, self.initial_y + self.letter.start_fall_y - self.height]
        window.blit(self.surface, self.pos)

class SoundManager:
    DELAY_BETWEEN_WORD_SOUNDS_S = 0.3

    def __init__(self):
        self.sound_queue: asyncio.Queue = asyncio.Queue()
        self.start_sound = pygame.mixer.Sound("./sounds/start.wav")
        self.crash_sound = pygame.mixer.Sound("./sounds/ping.wav")
        self.crash_sound.set_volume(0.8)
        self.chunk_sound = pygame.mixer.Sound("./sounds/chunk.wav")
        self.game_over_sound = pygame.mixer.Sound("./sounds/game_over.wav")
        self.bloop_sound = pygame.mixer.Sound("./sounds/bloop.wav")
        self.bloop_sound.set_volume(0.2)
        
        for n in range(11):
            letter_beeps.append(pygame.mixer.Sound(f"sounds/{n}.wav"))
            
        self.sound_queue_task = asyncio.create_task(self.play_sounds_in_queue(), name="word sound player")

    async def play_sounds_in_queue(self) -> None:
        pygame.mixer.set_reserved(2)
        delay_between_words_s = self.DELAY_BETWEEN_WORD_SOUNDS_S
        last_sound_time = datetime(year=1, month=1, day=1)
        while True:
            try:
                soundfile = await self.sound_queue.get()
                async with aiofiles.open(soundfile, mode='rb') as f:
                    s = pygame.mixer.Sound(buffer=await f.read())
                    now = datetime.now()
                    time_since_last_sound_s = (now - last_sound_time).total_seconds()
                    time_to_sleep_s = delay_between_words_s - time_since_last_sound_s
                    await asyncio.sleep(time_to_sleep_s)
                    channel = pygame.mixer.find_channel(force=True)
                    channel.queue(s)
                    last_sound_time = datetime.now()
            except Exception as e:
                print(f"error playing sound {soundfile}: {e}")
                continue

    async def queue_word_sound(self, word: str, player: int) -> None:
        await self.sound_queue.put(f"word_sounds_{player}/{word.lower()}.wav")

    def play_start(self) -> None:
        pygame.mixer.Sound.play(self.start_sound)

    def play_crash(self) -> None:
        pygame.mixer.Sound.play(self.crash_sound)

    def play_chunk(self) -> None:
        pygame.mixer.Sound.play(self.chunk_sound)

    def play_game_over(self) -> None:
        pygame.mixer.Sound.play(self.game_over_sound)

    def play_bloop(self) -> None:
        pygame.mixer.Sound.play(self.bloop_sound)

class Game:
    def __init__(self, the_app: app.App, letter_font: pygame.freetype.Font) -> None:
        self._app = the_app
        if PLAYER_COUNT == 1:
            self.scores = [Score(-1)]
        else:
            self.scores = [Score(player) for player in range(PLAYER_COUNT)]
        letter_y = self.scores[0].get_size()[1] + 4
        self.rack_metrics = RackMetrics()
        self.letter = Letter(letter_font, letter_y, self.rack_metrics)
        if PLAYER_COUNT == 1:
            self.racks = [Rack(self.rack_metrics, self.letter, -1)]
        else:
            self.racks = [Rack(self.rack_metrics, self.letter, player) for player in range(PLAYER_COUNT)]
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

        events.on(f"game.stage_guess")(self.stage_guess)
        events.on(f"game.old_guess")(self.old_guess)
        events.on(f"game.bad_guess")(self.bad_guess)
        events.on(f"game.next_tile")(self.next_tile)
        events.on(f"game.abort")(self.abort)
        events.on(f"game.start")(self.start)
        events.on(f"input.remaining_previous_guesses")(self.update_remaining_guesses)
        events.on(f"input.update_previous_guesses")(self.update_previous_guesses)
        events.on(f"input.add_guess")(self.add_guess)
        events.on(f"rack.update_rack")(self.update_rack)
        events.on(f"rack.update_letter")(self.update_letter)

    async def update_rack(self, tiles: list[tiles.Tile], highlight_length: int, guess_length: int, player: int) -> None:
        await self.racks[player].update_rack(tiles, highlight_length, guess_length)

    async def update_letter(self, changed_tile: tiles.Tile, player: int) -> None:
        await self.racks[player].update_letter(changed_tile)

    async def old_guess(self, old_guess: str, player: int) -> None:
        self.racks[player].guess_type = GuessType.OLD
        self.previous_guesses_display.old_guess(old_guess)

    async def bad_guess(self, player: int) -> None:
        self.racks[player].guess_type = GuessType.BAD

    async def abort(self) -> None:
        self.aborted = True

    async def start(self) -> None:
        self.guess_to_player = {}
        self.previous_guesses_display = PreviousGuessesDisplay(PreviousGuessesDisplay.FONT_SIZE, self.guess_to_player)
        self.remaining_previous_guesses_display = RemainingPreviousGuessesDisplay(
            PreviousGuessesDisplay.FONT_SIZE - FONT_SIZE_DELTA, self.guess_to_player)
        self.letter.start()
        for score in self.scores:
            score.start()
        for rack in self.racks:
            rack.start()
        self.running = True
        now_s = pygame.time.get_ticks() / 1000
        self.stop_time_s = -1000
        self.last_letter_time_s = now_s
        self.start_time_s = now_s
        await self._app.start()
        self.sound_manager.play_start()

    async def stage_guess(self, score: int, last_guess: str, player: int) -> None:
        await self.sound_manager.queue_word_sound(last_guess, player)
        self.racks[player].guess_type = GuessType.GOOD
        self.shields.append(Shield(self.rack_metrics.get_rect().topleft, last_guess, score, player))

    async def accept_letter(self) -> None:
        await self._app.accept_new_letter(self.letter.letter, self.letter.letter_index())
        self.letter.letter = ""
        self.last_letter_time_s = pygame.time.get_ticks()/1000

    async def stop(self) -> None:
        self.sound_manager.play_game_over()
        logger.info("GAME OVER")
        for rack in self.racks:
            rack.stop()
        self.running = False
        now_s = pygame.time.get_ticks() / 1000
        self.stop_time_s = now_s
        self.duration_log_f.write(
            f"{self.scores[0].score},{now_s-self.start_time_s}\n")
        self.duration_log_f.flush()
        await self._app.stop()
        logger.info("GAME OVER OVER")

    async def next_tile(self, next_letter: str) -> None:
        if self.letter.get_screen_bottom_y() + Letter.Y_INCREMENT*3 > self.rack_metrics.get_rect().y:
            next_letter = "!"
        self.letter.change_letter(next_letter)

    def resize_previous_guesses(self) -> None:
        font_size = (cast(float, self.previous_guesses_display.font.size)*4.0)/5.0
        self.previous_guesses_display = PreviousGuessesDisplay.from_instance(
            self.previous_guesses_display, max(1, int(font_size)))
        self.remaining_previous_guesses_display = RemainingPreviousGuessesDisplay.from_instance(
            self.remaining_previous_guesses_display, int(font_size - FONT_SIZE_DELTA))
        self.previous_guesses_display.draw()
        self.remaining_previous_guesses_display.draw()

    def exec_with_resize(self, f):
        retry_count = 0
        while True:
            try:
                retry_count += 1
                if retry_count > 2:
                    raise Exception("too many TextRectException")
                return f()
            except textrect.TextRectException as e:
                # print(f"resize_previous_guesses: {e}")
                self.resize_previous_guesses()

    async def add_guess(self, previous_guesses: list[str], guess: str, player: int) -> None:
        self.guess_to_player[guess] = player
        self.exec_with_resize(lambda: self.previous_guesses_display.add_guess(previous_guesses, guess, player))

    async def update_previous_guesses(self, previous_guesses: list[str]) -> None:
        self.exec_with_resize(lambda: self.previous_guesses_display.update_previous_guesses(previous_guesses))

    async def update_remaining_guesses(self, previous_guesses: list[str]) -> None:
        self.exec_with_resize(lambda: self.remaining_previous_guesses_display.update_remaining_guesses(previous_guesses))

    def update_previous_guesses_with_resizing(self, window: pygame.Surface) -> None:
        def update_all_previous_guesses(self, window: pygame.Surface) -> None:
            self.previous_guesses_display.update(window)
            self.remaining_previous_guesses_display.update(
                window, self.previous_guesses_display.surface.get_bounding_rect().height)

        self.exec_with_resize(lambda: update_all_previous_guesses(self, window))

    async def update(self, window: pygame.Surface) -> None:
        window.set_alpha(255)
        self.update_previous_guesses_with_resizing(window)
        self.letter_source.update(window)

        if self.running:
            self.letter.update(window)
            await self._app.letter_lock(self.letter.letter_index(), self.letter.locked_on)

        for rack in self.racks:
            rack.update(window)
        for shield in self.shields:
            shield.update(window)
            if shield.rect.y <= self.letter.get_screen_bottom_y():
                shield.letter_collision()
                self.letter.shield_collision()
                self.scores[shield.player].update_score(shield.score)
                self._app.add_guess(shield.letters, shield.player)
                self.sound_manager.play_crash()

        self.shields[:] = [s for s in self.shields if s.active]
        for score in self.scores:
            score.update(window)

        # letter collide with rack
        if self.running and self.letter.get_screen_bottom_y() > self.rack_metrics.get_rect().y:
            if self.letter.letter == "!":
                await self.stop()
            else:
                self.sound_manager.play_chunk()
                self.letter.new_fall()
                await self.accept_letter()

class BlockWordsPygame():
    def __init__(self) -> None:
        self._window = pygame.display.set_mode(
            (SCREEN_WIDTH*SCALING_FACTOR, SCREEN_HEIGHT*SCALING_FACTOR))
        self.letter_font = pygame.freetype.SysFont(FONT, RackMetrics.LETTER_SIZE)
        self.keyboard_guess = ""

    async def handle_mqtt_message(self, topic: aiomqtt.Topic) -> None:
        if topic.matches("app/start"):
            events.trigger("game.start")
        elif topic.matches("app/abort"):
            events.trigger("game.abort")

    async def main(self, the_app: app.App, subscribe_client: aiomqtt.Client, start: bool, args: argparse.Namespace, keyboard_player_number: int) -> None:
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        clock = Clock()
        keyboard_guess = ""
        await subscribe_client.subscribe("app/#")

        joystick = None
        if pygame.joystick.get_count() > 0:
            joystick = pygame.joystick.Joystick(0)
            print(f"Game controller connected: {joystick.get_name()}")

        add_sound = pygame.mixer.Sound("sounds/add.wav")
        erase_sound = pygame.mixer.Sound("sounds/erase.wav")
        cleared_sound = pygame.mixer.Sound("sounds/cleared.wav")
        left_sound = pygame.mixer.Sound("sounds/left.wav")
        right_sound = pygame.mixer.Sound("sounds/right.wav")
        
        left_sound.set_volume(0.5)
        right_sound.set_volume(0.5)

        game = Game(the_app, self.letter_font)
        keyboard_rack = game.racks[keyboard_player_number]
        
        async def handle_space_action():
            if keyboard_rack.cursor_position >= len(self.keyboard_guess):
                # Insert letter at cursor position into the guess
                letter_at_cursor = keyboard_rack.letters()[keyboard_rack.cursor_position]
                self.keyboard_guess += letter_at_cursor
                pygame.mixer.Sound.play(add_sound)
            else:
                # Remove letter at cursor position from the guess
                self.keyboard_guess = self.keyboard_guess[:keyboard_rack.cursor_position] + self.keyboard_guess[keyboard_rack.cursor_position + 1:]
                if keyboard_rack.select_count > 0:
                    pygame.mixer.Sound.play(erase_sound)
            if keyboard_rack.cursor_position >= len(self.keyboard_guess):
                keyboard_rack.cursor_position = max(len(self.keyboard_guess) - 1, 0)
            keyboard_rack.select_count = len(self.keyboard_guess)
            if keyboard_rack.select_count == 0:
                pygame.mixer.Sound.play(cleared_sound)
            await the_app.guess_word_keyboard(self.keyboard_guess, keyboard_player_number)
        
        async def start_game():
            self.keyboard_guess = ""
            keyboard_rack.cursor_position = 0
            keyboard_rack.select_count = 0
            # clear out the last guess
            await the_app.guess_word_keyboard("", keyboard_player_number)            
            await game.start()
        
        def handle_left_movement():
            if keyboard_rack.cursor_position > 0:
                keyboard_rack.cursor_position -= 1
                keyboard_rack.draw()
                pygame.mixer.Sound.play(left_sound)
        
        def handle_right_movement():
            if keyboard_rack.cursor_position < tiles.MAX_LETTERS - 1:
                keyboard_rack.cursor_position += 1
                keyboard_rack.draw()
                pygame.mixer.Sound.play(right_sound)
        
        def handle_return_action():
            self.keyboard_guess = ""
            keyboard_rack.cursor_position = 0
            keyboard_rack.select_count = len(self.keyboard_guess)
            pygame.mixer.Sound.play(cleared_sound)
            keyboard_rack.draw()
        
        while True:
            current_time_s = pygame.time.get_ticks() / 1000
            if start and not game.running and current_time_s - game.stop_time_s > 120:
                await game.start()
            if game.aborted:
                return
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    key = pygame.key.name(event.key).upper()
                    if key == "ESCAPE":
                        await start_game()
                    elif key == "LEFT":
                        handle_left_movement()
                    elif key == "RIGHT":
                        handle_right_movement()
                    elif key == "SPACE":
                        await handle_space_action()
                    elif key == "BACKSPACE":
                        if self.keyboard_guess:
                            self.keyboard_guess = self.keyboard_guess[:-1]
                            keyboard_rack.select_count = len(self.keyboard_guess)
                            keyboard_rack.draw()
                    elif key == "RETURN":
                        handle_return_action()
                    elif len(key) == 1:
                        remaining_letters = list(keyboard_rack.letters())
                        for l in self.keyboard_guess:
                            if l in remaining_letters:
                                remaining_letters.remove(l)
                        if key not in remaining_letters:
                            self.keyboard_guess = ""
                            keyboard_rack.select_count = len(self.keyboard_guess)
                            remaining_letters = list(keyboard_rack.letters())
                        if key in remaining_letters:
                            self.keyboard_guess += key
                            await the_app.guess_word_keyboard(self.keyboard_guess, keyboard_player_number)
                            keyboard_rack.select_count = len(self.keyboard_guess)
                            logger.info(f"key: {str(key)} {self.keyboard_guess}")
                
                # Handle game controller events
                if game.running and joystick and event.type == pygame.JOYAXISMOTION:
                    if event.axis == 0:  # Left stick horizontal
                        if event.value < -0.5:  # Left
                            handle_left_movement()
                        elif event.value > 0.5:  # Right
                            handle_right_movement()
                
                if game.running and joystick and event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 1:  # A button (usually button 0)
                        await handle_space_action()
                    elif event.button == 2:  # B button - same as return
                        handle_return_action()
                    elif event.button == 9:
                        await start_game()

            screen.fill((0, 0, 0))
            await game.update(screen)
            hub75.update(screen)
            pygame.transform.scale(screen,
                self._window.get_rect().size, dest_surface=self._window)
            pygame.display.flip()
            await clock.tick(TICKS_PER_SECOND)
