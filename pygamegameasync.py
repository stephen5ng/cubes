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

class Rack():
    LETTER_TRANSITION_DURATION_MS = 1500
    GUESS_TRANSITION_DURATION_MS = 800

    LETTER_SIZE = 25
    LETTER_COUNT = 6
    COLOR = Color("green")

    def __init__(self):
        self.font = pygame.freetype.SysFont(FONT, Rack.LETTER_SIZE)
        self.letters = ""
        self.running = False
        self.letter_width, self.letter_height = self.font.get_rect("A").size
        events.on(f"rack.change_rack")(self.change_rack)
        events.on(f"rack.update_letter")(self.update_letter)
        self.transition_position = -1
        self.last_update_letter_ms = -Rack.LETTER_TRANSITION_DURATION_MS
        self.transition_color = Rack.COLOR
        self.transition_letter = ""
        self.easing = easing_functions.QuinticEaseInOut(start=0, end = 255, duration = 1)

        self.last_guess_ms = -Rack.GUESS_TRANSITION_DURATION_MS
        self.highlight_range = (0, -2)
        self.draw()

    def _render_letter(self, position, letter, color):
        margin = (self.letter_width - self.font.get_rect(letter).width) / 2
        self.font.render_to(self.surface, (self.letter_width*position + margin, 0), letter, color)

    def draw(self):
        letters = self.letters
        if self.running:
            self.surface = pygame.Surface((self.letter_width*tiles.MAX_LETTERS, self.letter_height))
            for ix, letter in enumerate(letters):
                self._render_letter(ix, letter, Rack.COLOR)
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

    async def change_rack(self, letters, highlight_range):
        self.letters = letters
        self.highlight_range = highlight_range
        self.last_guess_ms = pygame.time.get_ticks()
        # print(f"highlight {highlight_range}")
        self.draw()

    async def update_letter(self, letter, position):
        self.letters = self.letters[:position] + letter + self.letters[position + 1:]
        self.last_update_letter_ms = pygame.time.get_ticks()
        self.transition_position = position
        self.transition_letter = letter
        self.draw()

    def update(self, window):
        def get_alpha(last_update, duration):
            remaining_ms = duration - (pygame.time.get_ticks() - last_update)
            if 0 < remaining_ms < duration:
                return int(self.easing(remaining_ms / duration))
            return 0

        trans_remaining_ms = Rack.LETTER_TRANSITION_DURATION_MS - (pygame.time.get_ticks() - self.last_update_letter_ms)
        alpha = get_alpha(self.last_update_letter_ms, Rack.LETTER_TRANSITION_DURATION_MS)
        if alpha:
            self.draw()
            color = Color(Letter.COLOR)
            color.a = alpha
            self._render_letter(self.transition_position, self.transition_letter, color)

        alpha = get_alpha(self.last_guess_ms, Rack.GUESS_TRANSITION_DURATION_MS)
        if alpha:
            self.draw()
            for ix in range(self.highlight_range[0], self.highlight_range[0]+self.highlight_range[1]):
                color = Color(Shield.COLOR)
                color.a = alpha
                self._render_letter(ix, self.letters[ix], color)

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
        self.draw()

    def draw(self):
        self.surface = self.font.render(self.letters, Shield.COLOR)[0]
        self.pos[0] = SCREEN_WIDTH/2 - self.surface.get_width()/2

    def update(self, window):
        if self.letters:
            self.pos[1] += self.speed
            self.speed *= 1.05
            window.blit(self.surface, self.pos)

            # Get the tightest rectangle around the content for collision detection.
            self.rect = self.surface.get_bounding_rect().move(self.pos[0], self.pos[1])

    def letter_collision(self):
        self.letters = None
        self.pos[1] = SCREEN_HEIGHT

class InProgressShield():
    X_OFFSET = 0
    COLOR = Color("grey")

    def __init__(self, y):
        self.baseline = SCREEN_HEIGHT - Rack.LETTER_SIZE
        self.color = InProgressShield.COLOR
        self.font = pygame.freetype.SysFont("Arial", 12)
        self.letters = ""
        self.y_midpoint = y
        self.speed = 0
        self.draw()
        self.pos = [InProgressShield.X_OFFSET,
            self.y_midpoint - self.surface.get_height()/2]

    def draw(self):
        self.surface = self.font.render(self.letters, InProgressShield.COLOR)[0]

    def update_letters(self, letters):
        self.letters = letters
        self.draw()

    def update(self, window):
        window.blit(self.surface, self.pos)

class Score():
    def __init__(self):
        self.font = pygame.font.SysFont(FONT, Rack.LETTER_SIZE)
        self.pos = [0, 0]
        self.start()
        self.draw()

    def start(self):
        self.score = 0
        self.draw()

    def draw(self):
        self.surface = self.font.render(str(self.score), Letter.ANTIALIAS, (255, 255, 255))
        self.pos[0] = SCREEN_WIDTH/2 - self.surface.get_width()/2

    def update_score(self, score):
        self.score += score
        self.draw()

    def update(self, window):
        window.blit(self.surface, self.pos)

class PreviousGuesses():
    COLOR = Color("skyblue")
    FONT = "Arial"
    FONT_SIZE = 12
    POSITION_TOP = 24

    def __init__(self):
        self.fontsize = PreviousGuesses.FONT_SIZE
        self.color = PreviousGuesses.COLOR
        self.font = pygame.font.SysFont(PreviousGuesses.FONT, self.fontsize)
        self.previous_guesses = ""
        events.on(f"input.previous_guesses")(self.update_previous_guesses)
        self.draw()

    async def update_previous_guesses(self, previous_guesses):
        self.previous_guesses = previous_guesses
        self.draw()

    def draw(self):
        try:
            self.surface = textrect.render_textrect(self.previous_guesses, self.font,
                pygame.Rect(0,0, SCREEN_WIDTH, SCREEN_HEIGHT),
                self.color, Color("black"), 0)
            return
        except textrect.TextRectException:
            logger.warning("Too many guesses to display!")

    def update(self, window):
        window.blit(self.surface, [0, PreviousGuesses.POSITION_TOP])


class RemainingPreviousGuesses(PreviousGuesses):
    COLOR = Color("grey")
    FONT = "Arial"
    FONT_SIZE = 10
    TOP_GAP = 3

    def __init__(self):
        self.fontsize = RemainingPreviousGuesses.FONT_SIZE
        self.font = pygame.font.SysFont(RemainingPreviousGuesses.FONT, self.fontsize)
        self.color = RemainingPreviousGuesses.COLOR
        self.previous_guesses = ""
        events.on(f"input.remaining_previous_guesses")(self.update_previous_guesses)
        self.draw()

    def update(self, window, height):
        window.blit(self.surface,
            [0, height + PreviousGuesses.POSITION_TOP + RemainingPreviousGuesses.TOP_GAP])

class LetterSource():
    COLOR = Color("yellow")
    def __init__(self, letter):
        self.letter = letter

    def update(self, window):
        bounding_rect = self.letter.surface.get_bounding_rect()
        self.pos = [SCREEN_WIDTH/2 - self.letter.all_letters_width()/2,
            self.letter.height + bounding_rect.y]
        size = [self.letter.all_letters_width(), 1]
        surf = pygame.Surface(size, pygame.SRCALPHA)
        color = LetterSource.COLOR
        color.a = 128
        surf.fill(color)
        window.blit(surf, self.pos)

class Letter():
    LETTER_SIZE = 25
    ANTIALIAS = 1
    COLOR = Color("yellow")
    # ACCELERATION = 1.01
    ACCELERATION = 1.01
    # acc: 1.1, robot score: 100
    # acc: 1.005, robot score: 544

    # ACCELERATION = 1.005
    INITIAL_SPEED = 0.020
    INITIAL_HEIGHT = 20
    ROUNDS = 15
    HEIGHT_INCREMENT = SCREEN_HEIGHT // ROUNDS
    COLUMN_SHIFT_INTERVAL_MS = 10000

    def __init__(self):
        self.font = pygame.font.SysFont(FONT, Letter.LETTER_SIZE)
        self.width = self.font.size("A")[0]
        self.next_interval_ms = 1
        self.fraction_complete = 0
        self.start()
        self.start_fall_time_ms = pygame.time.get_ticks()
        self.draw()

    def start(self):
        self.letter = ""
        self.letter_ix = 0
        self.height = Letter.INITIAL_HEIGHT
        self.column_move_direction = 1
        self.next_column_move_time_ms = pygame.time.get_ticks()
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.pos = [0, self.height]
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
        self.surface = self.font.render(self.letter, Letter.ANTIALIAS, Letter.COLOR)

        now_ms = pygame.time.get_ticks()
        remaining_ms = max(0, self.next_column_move_time_ms - now_ms)
        self.fraction_complete = 1.0 - remaining_ms/self.next_interval_ms
        boost_x = self.column_move_direction*(self.width*self.fraction_complete - self.width)
        self.pos[0] = ((SCREEN_WIDTH/2 - self.all_letters_width()/2) +
            self.width*self.letter_ix + boost_x)
        self.rect = self.surface.get_bounding_rect().move(
            self.pos[0], self.pos[1]).inflate(SCREEN_WIDTH, 0)

    def shield_collision(self):
        new_pos = self.height + (self.pos[1] - self.height)/2
        logger.debug(f"---------- {self.height}, {self.pos[1]}, {new_pos}, {self.pos[1] - new_pos}")

        self.pos[1] = self.height + (self.pos[1] - self.height)/2
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

            percent_complete = ((self.pos[1] - Letter.INITIAL_HEIGHT) /
                (SCREEN_HEIGHT - (Letter.INITIAL_HEIGHT + 25)))
            self.next_interval_ms = 100 + Letter.COLUMN_SHIFT_INTERVAL_MS*percent_complete
            self.next_column_move_time_ms = now_ms + self.next_interval_ms

    def reset(self):
        self.height += Letter.HEIGHT_INCREMENT
        self.pos[1] = self.height
        self.start_fall_time_ms = pygame.time.get_ticks()

class Game:
    def __init__(self, mqtt_client, the_app):
        global chunk_sound, crash_sound, wilhelm_sound
        self._mqtt_client = mqtt_client
        self._app = the_app
        self.letter = Letter()
        self.rack = Rack()
        self.previous_guesses = PreviousGuesses()
        self.remaining_previous_guesses = RemainingPreviousGuesses()
        self.score = Score()
        self.letter_source = LetterSource(self.letter)
        self.shields = []
        self.in_progress_shield = InProgressShield(self.rack.get_midpoint())
        self.running = False
        self.game_log_f = open("gamelog.csv", "a")
        self.duration_log_f = open("durationlog.csv", "a")
        crash_sound = pygame.mixer.Sound("./sounds/ping.wav")
        chunk_sound = pygame.mixer.Sound("./sounds/chunk.wav")
        wilhelm_sound = pygame.mixer.Sound("./sounds/wilhelm.wav")
        wilhelm_sound.set_volume(0.1)

        for n in range(11):
            letter_beeps.append(pygame.mixer.Sound(f"sounds/{n}.wav"))
        events.on(f"game.current_score")(self.score_points)
        events.on(f"game.next_tile")(self.next_tile)
        events.on(f"game.abort")(self.abort)

    async def abort(self):
        pygame.quit()

    async def start(self):
        self.letter.start()
        self.score.start()
        self.rack.start()
        self.running = True
        now_s = pygame.time.get_ticks() / 1000
        self.last_letter_time_s = now_s
        self.start_time_s = now_s
        await self._app.start()
        pygame.mixer.Sound.play(crash_sound)

    async def score_points(self, score, last_guess):
        self.in_progress_shield.update_letters(last_guess)
        if score <= 0:
            return

        async with aiofiles.open(f"word_sounds/{last_guess.lower()}.wav", mode='rb') as f:
            ff = await f.read()
            s = pygame.mixer.Sound(buffer=ff)
            pygame.mixer.Sound.play(s)

        logger.info(f"SCORING POINTS: {score} {last_guess}")
        now_s = pygame.time.get_ticks()/1000
        self.game_log_f.write(
            f"{now_s-self.start_time_s},{now_s-self.last_letter_time_s},{self.score.score}\n")
        self.game_log_f.flush()
        # print(f"creating shield with word {last_guess}")
        self.shields.append(Shield(last_guess, score))

    async def accept_letter(self):
        await self._app.accept_new_letter(self.letter.letter, self.letter.letter_index())
        self.letter.letter = ""
        self.last_letter_time_s = pygame.time.get_ticks()/1000

    async def stop(self):
        pygame.mixer.Sound.play(wilhelm_sound)
        logger.info("GAME OVER")
        self.rack.stop()
        self.running = False
        now_s = pygame.time.get_ticks() / 1000
        self.duration_log_f.write(
            f"{Letter.ACCELERATION},{Letter.INITIAL_SPEED},{self.score.score},{now_s-self.start_time_s}\n")
        self.duration_log_f.flush()
        self._app.stop()
        logger.info("GAME OVER OVER")

    async def next_tile(self, next_letter):
        if self.letter.height + self.letter.rect.height + Letter.HEIGHT_INCREMENT*3 > self.rack.pos[1]:
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
        if self.running:
            self.in_progress_shield.update(window)
        for shield in self.shields:
            shield.update(window)
            # print(f"checking collision: {shield.rect}, {self.letter.rect}")
            if shield.rect.colliderect(self.letter.rect):
                # print(f"collided: {shield.letters}")
                shield.letter_collision()
                self.letter.shield_collision()
                self.score.update_score(shield.score)
                pygame.mixer.Sound.play(crash_sound)

        self.shields[:] = [s for s in self.shields if s.letters]
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

async def main(the_app, mqtt_client, start, args):
    window = pygame.display.set_mode(
        (SCREEN_WIDTH*SCALING_FACTOR, SCREEN_HEIGHT*SCALING_FACTOR))
    screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

    clock = Clock()
    keyboard_guess = ""
    await mqtt_client.subscribe("app/#")

    game = Game(mqtt_client, the_app)

    while True:
        if start and not game.running:
            await game.start()
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
                    keyboard_guess = keyboard_guess[:-1]
                elif key == "RETURN":
                    await the_app.guess_word_keyboard(keyboard_guess)
                    logger.info("RETURN CASE DONE")
                    keyboard_guess = ""
                elif len(key) == 1:
                    keyboard_guess += key
                    logger.info(f"key: {str(key)} {keyboard_guess}")
                game.in_progress_shield.update_letters(keyboard_guess)

        screen.fill((0, 0, 0))
        await game.update(screen)
        if platform.system() != "Darwin":
            pixels = image_to_string(screen, "RGB")
            img = Image.frombytes("RGB", (screen.get_width(), screen.get_height()), pixels)
#                print(f"size: {img.size}")
            img = img.rotate(90, Image.NEAREST, expand=1)
#                print(f"rotated size: {img.size}")
            offscreen_canvas.SetImage(img)
            matrix.SwapOnVSync(offscreen_canvas)
        window.blit(pygame.transform.scale(screen, window.get_rect().size), (0, 0))
        pygame.display.flip()
        await clock.tick(TICKS_PER_SECOND)
