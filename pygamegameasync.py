# From https://python-forum.io/thread-23029.html

import platform
if platform.system() != "Darwin":
    from rgbmatrix import graphics
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    from runtext import RunText
import aiofiles
import aiomqtt
import argparse
import asyncio
from datetime import datetime
import easing_functions
import json
import logging
import math
import os
from paho.mqtt import client as mqtt_client
from PIL import Image
import pygame
import pygame.freetype
from pygame import Color
import sys
import textrect
import time

import app
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

crash_sound = None
chunk_sound = None
game_mqtt_client = None
wilhelm_sound = None
letter_beeps = []

matrix = None
offscreen_canvas = None

def get_alpha(easing, last_update, duration):
    remaining_ms = duration - (pygame.time.get_ticks() - last_update)
    if 0 < remaining_ms < duration:
        return int(easing(remaining_ms / duration))
    return 0

class Rack():
    LETTER_TRANSITION_DURATION_MS = 4000
    GUESS_TRANSITION_DURATION_MS = 800

    LETTER_SIZE = 25
    LETTER_COUNT = 6
    LETTER_BORDER = 4
    COLOR = Color("green")

    def __init__(self, falling_letter):
        self.font = pygame.freetype.SysFont(FONT, Rack.LETTER_SIZE)
        self.tiles = []
        self.running = False
        self.letter_width, self.letter_height = self.font.get_rect("A").size
        self.letter_width += Rack.LETTER_BORDER
        self.letter_height += Rack.LETTER_BORDER
        self.border = " "
        events.on(f"rack.update_rack")(self.update_rack)
        events.on(f"rack.update_letter")(self.update_letter)
        self.last_update_letter_ms = -Rack.LETTER_TRANSITION_DURATION_MS
        self.transition_color = Rack.COLOR
        self.easing = easing_functions.QuinticEaseInOut(start=0, end=255, duration=1)
        self.last_guess_ms = -Rack.GUESS_TRANSITION_DURATION_MS
        self.highlight_length = 0
        self.select_count = 0
        self.transition_tile = None
        self.falling_letter = falling_letter
        self.draw()

    def _render_letter(self, position, letter, color):
        color = Color(color)
        distance = self.pos[1] - (self.falling_letter.rect.y + self.falling_letter.rect.height)
        if self.falling_letter.letter == "!":
            if distance % 3 == 0:
                color.a = 100
        elif self.falling_letter.letter_index() == position:
            if distance < 100:
                if distance % 3 == 0:
                    color.a = 40
        margin = (self.letter_width - self.font.get_rect(letter).width) / 2
        self.font.render_to(self.surface,
            (self.letter_width*position + margin, Rack.LETTER_BORDER/2), letter, color)

    def letters(self):
        return ''.join([l.letter for l in self.tiles])

    def draw(self):
        if self.running:
            self.surface = pygame.Surface((self.letter_width*tiles.MAX_LETTERS, self.letter_height))
            for ix, letter in enumerate(self.letters()):
                self._render_letter(ix, letter, Rack.COLOR)
            pygame.draw.rect(self.surface, Color("grey"),
                (0, 0, self.letter_width*self.select_count, self.letter_height),
                1)
        else:
            self.surface = self.font.render("GAME OVER", Rack.COLOR)[0]
        self.pos = ((SCREEN_WIDTH/2 - self.surface.get_width()/2),
            (SCREEN_HEIGHT - self.surface.get_height()))

    def start(self):
        self.running = True
        self.draw()

    def stop(self):
        self.running = False
        self.draw()

    def get_midpoint(self):
        return self.pos[1] + self.surface.get_height()/2

    async def update_rack(self, tiles, highlight_length, guess_length):
        self.tiles = tiles
        self.highlight_length = highlight_length
        self.last_guess_ms = pygame.time.get_ticks()
        self.select_count = guess_length
        self.draw()

    async def update_letter(self, tile, position):
        self.tiles = self.tiles[:position] + [tile] + self.tiles[position + 1:]
        self.last_update_letter_ms = pygame.time.get_ticks()
        self.transition_tile = tile
        self.draw()

    def update(self, window):
        def make_color(color, alpha):
            new_color = Color(color)
            new_color.a = alpha
            return new_color

        self.draw()

        new_letter_alpha = get_alpha(self.easing,
            self.last_update_letter_ms, Rack.LETTER_TRANSITION_DURATION_MS)
        if new_letter_alpha:
            self._render_letter(
                self.tiles.index(self.transition_tile),
                self.transition_tile.letter,
                make_color(Letter.COLOR, new_letter_alpha))

        good_word_alpha = get_alpha(self.easing,
            self.last_guess_ms, Rack.GUESS_TRANSITION_DURATION_MS)
        if good_word_alpha:
            color = make_color(Shield.COLOR, good_word_alpha)
            letters = self.letters()
            for ix in range(0, self.highlight_length):
                self._render_letter(ix, letters[ix], color)

        window.blit(self.surface, self.pos)

class Shield():
    COLOR = Color("red")
    ACCELERATION = 1.05

    def __init__(self, letters, score):
        self.font = pygame.freetype.SysFont("Arial", int(2+math.log(1+score)*8))
        self.letters = letters
        self.baseline = SCREEN_HEIGHT - Rack.LETTER_SIZE
        self.pos = [SCREEN_WIDTH/2, self.baseline]
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.speed = -math.log(1+score) / 10
        self.score = score
        self.active = True
        self.draw()

    def draw(self):
        self.surface = self.font.render(self.letters, Shield.COLOR)[0]
        self.pos[0] = SCREEN_WIDTH/2 - self.surface.get_width()/2

    def update(self, window):
        if self.active:
            self.pos[1] += self.speed
            self.speed *= 1.05
            window.blit(self.surface, self.pos)

            # Get the tightest rectangle around the content for collision detection.
            self.rect = self.surface.get_bounding_rect().move(self.pos[0], self.pos[1])

    def letter_collision(self):
        self.active = False
        self.pos[1] = SCREEN_HEIGHT

class Score():
    COLOR = Color("WHITE")
    def __init__(self):
        self.font = pygame.freetype.SysFont(FONT, Rack.LETTER_SIZE)
        self.pos = [0, 0]
        self.start()
        self.draw()

    def start(self):
        self.score = 0
        self.draw()

    def draw(self):
        self.surface = self.font.render(str(self.score), Score.COLOR)[0]
        self.pos[0] = SCREEN_WIDTH/2 - self.surface.get_width()/2

    def update_score(self, score):
        self.score += score
        self.draw()

    def update(self, window):
        window.blit(self.surface, self.pos)

class LastGuessFader():
    FADE_DURATION_MS = 2000

    def __init__(self, last_update_ms, font, textrect, color):
        self.alpha = 255
        self.font = font
        self.textrect = textrect
        self.last_update_ms = last_update_ms
        self.easing = easing_functions.QuinticEaseInOut(start=0, end = 255, duration = 1)
        self.last_guess = ""
        self.color = color

    def render(self, previous_guesses, last_guess):
        self.last_guess = last_guess
        last_guess_rect = self.font.get_rect(last_guess)
        ix = previous_guesses.index(last_guess)
        up_thru_last_guess = ' '.join(previous_guesses[:ix+1])
        last_line_rect = self.textrect.get_last_rect(up_thru_last_guess)
        font_surf = self.font.render(last_guess, self.color)[0]
        self.last_guess_surface = pygame.Surface(font_surf.size, pygame.SRCALPHA)
        self.last_guess_surface.blit(font_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        self.last_guess_position = (
            last_line_rect.x + last_line_rect.width - last_guess_rect.width, last_line_rect.y)

    def blit(self, target):
        self.alpha = get_alpha(self.easing,
            self.last_update_ms, LastGuessFader.FADE_DURATION_MS if self.color == Shield.COLOR else 1000)
        if self.alpha:
            self.last_guess_surface.set_alpha(self.alpha)
            target.blit(self.last_guess_surface, self.last_guess_position)

class PreviousGuessesBase():
    COLOR = Color("skyblue")
    FONT = "Arial"

    def __init__(self, font_size, color):
        self.font = pygame.freetype.SysFont(PreviousGuessesBase.FONT, font_size)
        self.font.kerning = True
        self.previous_guesses = ""
        self.textrect = textrect.TextRectRenderer(self.font,
                pygame.Rect(0,0, SCREEN_WIDTH, SCREEN_HEIGHT),
                color)
        self.draw()

    async def update_previous_guesses(self, previous_guesses):
        self.previous_guesses = previous_guesses
        self.draw()

    def draw(self):
        try:
            self.surface = self.textrect.render(' '.join(self.previous_guesses))
        except textrect.TextRectException:
            logger.warning("Too many guesses to display!")

class PreviousGuesses(PreviousGuessesBase):
    COLOR = Color("skyblue")
    FONT_SIZE = 12
    POSITION_TOP = 24
    FADE_DURATION_NEW_GUESS = 2000
    FADE_DURATION_OLD_GUESS = 1000
    def __init__(self):
        super(PreviousGuesses, self).__init__(
            PreviousGuesses.FONT_SIZE,
            PreviousGuesses.COLOR)
        self.faders = []
        self.fader_inputs = []
        self.bloop_sound = pygame.mixer.Sound("./sounds/bloop.wav")
        events.on(f"input.add_guess")(self.add_guess)
        events.on(f"input.previous_guesses")(self.update_previous_guesses)
        events.on(f"game.flash_old_guess")(self.flash_old_guess)

    async def flash_old_guess(self, old_guess):
        self.fader_inputs.append(
            [old_guess, pygame.time.get_ticks(), LetterSource.COLOR, PreviousGuesses.FADE_DURATION_OLD_GUESS])
        await self.update_previous_guesses(self.previous_guesses)
        pygame.mixer.Sound.play(self.bloop_sound)

    async def add_guess(self, previous_guesses, last_guess):
        self.fader_inputs.append(
            [last_guess, pygame.time.get_ticks(), Shield.COLOR, PreviousGuesses.FADE_DURATION_NEW_GUESS])
        await self.update_previous_guesses(previous_guesses)

    async def update_previous_guesses(self, previous_guesses):
        self.faders = []
        for last_guess, last_update_ms, color, duration in self.fader_inputs:
            if last_guess in previous_guesses:
                fader = LastGuessFader(last_update_ms, self.font, self.textrect, color)
                fader.render(previous_guesses, last_guess)
                self.faders.append(fader)
        await super(PreviousGuesses, self).update_previous_guesses(previous_guesses)

    def update(self, window):
        surface_with_faders = self.surface.copy()
        for fader in self.faders:
            fader.blit(surface_with_faders)

        # remove finished faders
        self.faders[:] = [f for f in self.faders if f.alpha]
        fader_guesses = [f.last_guess for f in self.faders]

        # re-create fader_inputs for the faders that survived.
        self.fader_inputs = [f for f in self.fader_inputs if f[0] in fader_guesses]
        window.blit(surface_with_faders, [0, PreviousGuesses.POSITION_TOP])

class RemainingPreviousGuesses(PreviousGuessesBase):
    COLOR = Color("grey")
    FONT_SIZE = 10
    TOP_GAP = 3

    def __init__(self):
        super(RemainingPreviousGuesses, self).__init__(
            RemainingPreviousGuesses.FONT_SIZE,
            RemainingPreviousGuesses.COLOR)
        events.on(f"input.remaining_previous_guesses")(self.update_previous_guesses)

    def update(self, window, height):
        window.blit(self.surface,
            [0, height + PreviousGuesses.POSITION_TOP + RemainingPreviousGuesses.TOP_GAP])

class LetterSource():
    COLOR = Color("yellow")
    ALPHA = 128
    ANIMATION_DURAION_MS = 200
    MIN_HEIGHT = 1
    MAX_HEIGHT = 20
    def __init__(self, letter):
        self.last_y = 0
        self.height = LetterSource.MIN_HEIGHT
        self.letter = letter
        self.width = self.letter.all_letters_width()
        self.easing = easing_functions.QuinticEaseInOut(
            start=1, end=LetterSource.MAX_HEIGHT, duration =1)
        self.draw()

    def draw(self):
        size = [self.width, self.height]
        self.surface = pygame.Surface(size, pygame.SRCALPHA)
        self.surface.set_alpha(LetterSource.ALPHA)
        self.surface.fill(LetterSource.COLOR)

    def update(self, window):
        if self.last_y != self.letter.y:
            self.last_update = pygame.time.get_ticks()
            self.height = LetterSource.MAX_HEIGHT
            self.last_y = self.letter.y
            self.draw()
        elif self.height > LetterSource.MIN_HEIGHT:
            self.height = get_alpha(self.easing, self.last_update, LetterSource.ANIMATION_DURAION_MS)
            self.draw()
        self.pos = [SCREEN_WIDTH/2 - self.letter.all_letters_width()/2, self.letter.y-self.height]
        window.blit(self.surface, self.pos)

class Letter():
    LETTER_SIZE = 25
    ANTIALIAS = 1
    COLOR = Color("yellow")
    ACCELERATION = 1.01
    INITIAL_SPEED = 0.020
    INITIAL_Y = 20
    ROUNDS = 15
    Y_INCREMENT = SCREEN_HEIGHT // ROUNDS
    COLUMN_SHIFT_INTERVAL_MS = 10000

    def __init__(self):
        self.font = Letter.the_font
        self.width = self.font.get_rect("A").width + Rack.LETTER_BORDER
        self.next_interval_ms = 1
        self.fraction_complete = 0
        self.start()
        self.start_fall_time_ms = pygame.time.get_ticks()
        self.bounce_sound = pygame.mixer.Sound("sounds/bounce.wav")
        self.draw()

    def start(self):
        self.letter = ""
        self.letter_ix = 0
        self.y = Letter.INITIAL_Y
        self.column_move_direction = 1
        self.next_column_move_time_ms = pygame.time.get_ticks()
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.pos = [0, self.y]
        self.start_fall_time_ms = pygame.time.get_ticks()
        self.last_beep_time_ms = pygame.time.get_ticks()

    def stop(self):
        self.letter = ""

    def all_letters_width(self):
        return tiles.MAX_LETTERS*self.width

    def letter_index(self):
        if self.fraction_complete >= 0.5:
            return self.letter_ix
        return self.letter_ix - self.column_move_direction

    def draw(self):
        self.surface = self.font.render(self.letter, Letter.COLOR)[0]

        now_ms = pygame.time.get_ticks()
        remaining_ms = max(0, self.next_column_move_time_ms - now_ms)
        self.fraction_complete = 1.0 - remaining_ms/self.next_interval_ms
        boost_x = self.column_move_direction*(self.width*self.fraction_complete - self.width)
        self.pos[0] = ((SCREEN_WIDTH/2 - self.all_letters_width()/2) +
            self.width*self.letter_ix + boost_x)
        self.rect = self.surface.get_bounding_rect().move(
            self.pos[0], self.pos[1]).inflate(SCREEN_WIDTH, 0)

    def shield_collision(self):
        new_pos = self.y + (self.pos[1] - self.y)/2
        logger.debug(f"---------- {self.y}, {self.pos[1]}, {new_pos}, {self.pos[1] - new_pos}")

        self.pos[1] = self.y + (self.pos[1] - self.y)/2
        self.start_fall_time_ms = pygame.time.get_ticks()

    def change_letter(self, new_letter):
        self.letter = new_letter
        self.draw()

    def update(self, window, score):
        now_ms = pygame.time.get_ticks()
        time_since_last_fall_s = (now_ms - self.start_fall_time_ms)/1000.0
        dy = 0 if score < FREE_SCORE else Letter.INITIAL_SPEED * math.pow(Letter.ACCELERATION,
            time_since_last_fall_s*TICKS_PER_SECOND)
        self.pos[1] += dy
        distance_from_top = self.pos[1] / SCREEN_HEIGHT
        distance_from_bottom = 1 - distance_from_top
        # if now_ms > self.last_beep_time_ms + distance_from_bottom*distance_from_bottom*5:
        if now_ms > self.last_beep_time_ms + (distance_from_bottom*distance_from_bottom)*7000:
            # print(f"y: {self.pos[1]}, {distance_from_top}, {int(10*distance_from_top)}")
            pygame.mixer.Sound.play(letter_beeps[int(10*distance_from_top)])
            self.last_beep_time_ms = now_ms

        self.draw()

        window.blit(self.surface, self.pos)

        if now_ms > self.next_column_move_time_ms:
            self.letter_ix = self.letter_ix + self.column_move_direction
            if self.letter_ix < 0 or self.letter_ix >= tiles.MAX_LETTERS:
                self.column_move_direction *= -1
                self.letter_ix = self.letter_ix + self.column_move_direction*2
                pygame.mixer.Sound.play(self.bounce_sound)

            percent_complete = ((self.pos[1] - Letter.INITIAL_Y) /
                (SCREEN_HEIGHT - (Letter.INITIAL_Y + 25)))
            self.next_interval_ms = 100 + Letter.COLUMN_SHIFT_INTERVAL_MS*percent_complete
            self.next_column_move_time_ms = now_ms + self.next_interval_ms

    def reset(self):
        self.y += Letter.Y_INCREMENT
        self.pos[1] = self.y
        self.start_fall_time_ms = pygame.time.get_ticks()

class Game:
    DELAY_BETWEEN_WORD_SOUNDS_S = 0.3
    def __init__(self, mqtt_client, the_app):
        global chunk_sound, crash_sound, game_over_sound
        self._mqtt_client = mqtt_client
        self._app = the_app
        self.letter = Letter()
        self.rack = Rack(self.letter)
        self.previous_guesses = PreviousGuesses()
        self.remaining_previous_guesses = RemainingPreviousGuesses()
        self.score = Score()
        self.letter_source = LetterSource(self.letter)
        self.shields = []
        self.running = False
        self.aborted = False
        self.game_log_f = open("gamelog.csv", "a+")
        self.duration_log_f = open("durationlog.csv", "a+")
        self.sound_queue = asyncio.Queue()
        self.start_sound = pygame.mixer.Sound("./sounds/start.wav")
        crash_sound = pygame.mixer.Sound("./sounds/ping.wav")
        chunk_sound = pygame.mixer.Sound("./sounds/chunk.wav")
        game_over_sound = pygame.mixer.Sound("./sounds/game_over.wav")
        self.sound_queue_task = asyncio.create_task(self.play_sounds_in_queue(),
            name="word sound player")

        for n in range(11):
            letter_beeps.append(pygame.mixer.Sound(f"sounds/{n}.wav"))
        events.on(f"game.stage_guess")(self.stage_guess)
        events.on(f"game.next_tile")(self.next_tile)
        events.on(f"game.abort")(self.abort)
        events.on(f"game.start")(self.start)

    async def abort(self):
        self.aborted = True

    async def start(self):
        self.letter.start()
        self.score.start()
        self.rack.start()
        self.running = True
        now_s = pygame.time.get_ticks() / 1000
        self.last_letter_time_s = now_s
        self.start_time_s = now_s
        await self._app.start()
        pygame.mixer.Sound.play(self.start_sound)

    async def stage_guess(self, score, last_guess):
        await self.sound_queue.put(f"word_sounds/{last_guess.lower()}.wav")
        self.shields.append(Shield(last_guess, score))

    async def accept_letter(self):
        await self._app.accept_new_letter(self.letter.letter, self.letter.letter_index())
        self.letter.letter = ""
        self.last_letter_time_s = pygame.time.get_ticks()/1000

    async def stop(self):
        pygame.mixer.Sound.play(game_over_sound)
        logger.info("GAME OVER")
        self.rack.stop()
        self.running = False
        now_s = pygame.time.get_ticks() / 1000
        self.duration_log_f.write(
            f"{Letter.ACCELERATION},{Letter.INITIAL_SPEED},{self.score.score},{now_s-self.start_time_s}\n")
        self.duration_log_f.flush()
        await self._app.stop()
        logger.info("GAME OVER OVER")

    async def next_tile(self, next_letter):
        if self.letter.y + self.letter.rect.height + Letter.Y_INCREMENT*3 > self.rack.pos[1]:
            logger.info("Switching to !")
            next_letter = "!"
        self.letter.change_letter(next_letter)

    async def update(self, window):
        window.set_alpha(255)
        self.previous_guesses.update(window)
        self.remaining_previous_guesses.update(
            window, self.previous_guesses.surface.get_bounding_rect().height)
        self.letter_source.update(window)

        if self.running:
            self.letter.update(window, self.score.score)

        self.rack.update(window)
        for shield in self.shields:
            shield.update(window)
            # print(f"checking collision: {shield.rect}, {self.letter.rect}")
            if shield.rect.colliderect(self.letter.rect):
                # print(f"collided: {shield.letters}")
                shield.letter_collision()
                self.letter.shield_collision()
                self.score.update_score(shield.score)
                self._app.add_guess(shield.letters)
                pygame.mixer.Sound.play(crash_sound)

        self.shields[:] = [s for s in self.shields if s.active]
        self.score.update(window)

        # letter collide with rack
        if self.running and self.letter.rect.y + self.letter.rect.height >= self.rack.pos[1]:
            if self.letter.letter == "!":
                await self.stop()
            else:
                # logger.info(f"-->{self.letter.height}. {self.letter.rect.height}, {Letter.HEIGHT_INCREMENT}, {self.rack.pos[1]}")
                pygame.mixer.Sound.play(chunk_sound)
                self.letter.reset()
                await self.accept_letter()
                # os.system('python3 -c "import beepy; beepy.beep(1)"&')

    async def play_sounds_in_queue(self):
        try:
            delay_between_words_s = Game.DELAY_BETWEEN_WORD_SOUNDS_S
            last_sound_time = datetime(year=1, month=1, day=1)
            while True:
                soundfile = await self.sound_queue.get()
                async with aiofiles.open(soundfile, mode='rb') as f:
                    s = pygame.mixer.Sound(buffer=await f.read())
                    now = datetime.now()
                    time_since_last_sound_s = (now - last_sound_time).total_seconds()
                    if time_since_last_sound_s < delay_between_words_s:
                        await asyncio.sleep(delay_between_words_s - time_since_last_sound_s)
                    s.play()
                    last_sound_time = now
        except Exception as e:
            print(f"error playing sound {e}")
            raise e

class BlockWordsPygame():
    def __init__(self):
        self._window = pygame.display.set_mode(
            (SCREEN_WIDTH*SCALING_FACTOR, SCREEN_HEIGHT*SCALING_FACTOR))
        Letter.the_font = pygame.freetype.SysFont(FONT, Letter.LETTER_SIZE)

    async def handle_mqtt_message(self, topic, payload):
        if topic.matches("app/start"):
            events.trigger("game.start")
        elif topic.matches("app/abort"):
            events.trigger("game.abort")

    async def main(self, the_app, subscribe_client, start, args):
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        clock = Clock()
        keyboard_guess = ""
        await subscribe_client.subscribe("app/#")

        game = Game(mqtt_client, the_app)
        last_loop_time = time.time()

        while True:
            start_time = time.time()
            elapsed = start_time - last_loop_time
            # print(f"last_guess_interval: {last_guess_time:.4f}s {start_time:.4f}s")
            # print(f"last_guess_loop    : {(elapsed):.8f} seconds")
            l = int(math.log(1+elapsed*1000000))
            # print(f"last_guess_loop    : {(elapsed):.8f}s {'*'*l}")
            last_loop_time = start_time
            # print(".", end="")
            if start and not game.running:
                await game.start()
            if game.aborted:
                return
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    key = pygame.key.name(event.key).upper()
                    if key == "ESCAPE":
                        print("starting")
                        # pass
                        await game.start()
                    elif key == "BACKSPACE":
                        if keyboard_guess:
                            keyboard_guess = keyboard_guess[:-1]
                            game.rack.select_count = len(keyboard_guess)
                            game.rack.draw()
                    elif key == "RETURN":
                        keyboard_guess = ""
                        game.rack.select_count = len(keyboard_guess)
                        game.rack.draw()
                    elif len(key) == 1:
                        remaining_letters = list(game.rack.letters())
                        for l in keyboard_guess:
                            if l in remaining_letters:
                                remaining_letters.remove(l)
                        if key not in remaining_letters:
                            keyboard_guess = ""
                            game.rack.select_count = len(keyboard_guess)
                            remaining_letters = list(game.rack.letters())
                        if key in remaining_letters:
                            keyboard_guess += key
                            await the_app.guess_word_keyboard(keyboard_guess)
                            game.rack.select_count = len(keyboard_guess)
                            logger.info(f"key: {str(key)} {keyboard_guess}")

            screen.fill((0, 0, 0))
            await game.update(screen)
            if platform.system() != "Darwin":
                pixels = image_to_string(screen, "RGB")
                img = Image.frombytes("RGB", (screen.get_width(), screen.get_height()), pixels)
    #                print(f"size: {img.size}")
                img = img.rotate(270, Image.NEAREST, expand=1)
    #                print(f"rotated size: {img.size}")
                offscreen_canvas.SetImage(img)
                matrix.SwapOnVSync(offscreen_canvas)
            self._window.blit(pygame.transform.scale(screen,
                self._window.get_rect().size), (0, 0))
            pygame.display.flip()
            await clock.tick(TICKS_PER_SECOND)
