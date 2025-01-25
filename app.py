import aiomqtt
import asyncio
from collections import Counter
from datetime import datetime
from functools import wraps
import json
import logging
import os
from paho.mqtt import client as mqtt_client
import paho.mqtt.subscribe as subscribe
import random
import sys
import time
import psutil
import signal

import cubes_to_game
from dictionary import Dictionary
from pygameasync import events
import tiles
from scorecard import ScoreCard

MQTT_CLIENT_ID = 'game-server'
MQTT_CLIENT_PORT = 1883

my_open = open

logger = logging.getLogger("app:"+__name__)

UPDATE_TILES_REBROADCAST_S = 8

SCRABBLE_LETTER_SCORES = {
    'A': 1, 'B': 3, 'C': 3, 'D': 2, 'E': 1, 'F': 4,
    'G': 2, 'H': 4, 'I': 1, 'J': 8, 'K': 5, 'L': 1,
    'M': 3, 'N': 1, 'O': 1, 'P': 3, 'Q': 10, 'R': 1,
    'S': 1, 'T': 1, 'U': 1, 'V': 4, 'W': 4, 'X': 8,
    'Y': 4, 'Z': 10
}

class App:
    def __init__(self, client, publish_queue, dictionary):
        def make_guess_tiles_callback(the_app):
            async def guess_tiles_callback(guess, move_tiles):
                await the_app.guess_tiles(guess, move_tiles)
            return guess_tiles_callback

        self._dictionary = dictionary
        self._publish_queue = publish_queue
        self._last_guess = ""
        self._player_rack = tiles.Rack('?' * tiles.MAX_LETTERS)
        self._score_card = ScoreCard(self._player_rack, self._dictionary)
        cubes_to_game.set_guess_tiles_callback(make_guess_tiles_callback(self))
        self._running = False

    async def start(self):
        self._player_rack = self._dictionary.get_rack()
        self._update_next_tile(self._player_rack.next_letter())
        self._score_card = ScoreCard(self._player_rack, self._dictionary)
        await self.load_rack()
        self._update_rack_display(0, 0)
        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        await cubes_to_game.guess_last_tiles(self._publish_queue)
        self._running = True

    async def stop(self):
        self._player_rack = tiles.Rack(' ' * tiles.MAX_LETTERS)
        await self.load_rack()
        self._running = False

    async def load_rack(self):
        await cubes_to_game.load_rack(self._publish_queue, self._player_rack.get_tiles())

    async def accept_new_letter(self, next_letter, position):
        changed_tile = self._player_rack.replace_letter(next_letter, position)

        self._score_card.update_previous_guesses()
        await cubes_to_game.accept_new_letter(self._publish_queue, next_letter, changed_tile.id)

        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        events.trigger("rack.update_letter", changed_tile, position)
        self._update_next_tile(self._player_rack.next_letter())
        await self.guess_tiles(self._last_guess, False)

    def add_guess(self, guess):
        self._score_card.add_guess(guess)
        events.trigger("input.add_guess",
            self._score_card.get_previous_guesses(), guess)

        self._update_previous_guesses()

    async def guess_tiles(self, word_tile_ids, move_tiles):
        self._last_guess = word_tile_ids
        logger.info(f"guess_tiles: word_tile_ids {word_tile_ids}")
        if not self._running:
            logger.info(f"not running, bailing")
            return
        guess = self._player_rack.ids_to_letters(word_tile_ids)
        guess_tiles = self._player_rack.ids_to_tiles(word_tile_ids)

        if move_tiles:
            remaining_tiles = self._player_rack.get_tiles().copy()
            for guess_tile in guess_tiles:
                remaining_tiles.remove(guess_tile)
            self._player_rack.set_tiles(guess_tiles + remaining_tiles)

        if self._score_card.is_old_guess(guess):
            events.trigger("game.flash_old_guess", guess)
        elif self._score_card.is_good_guess(guess):
            await cubes_to_game.flash_good_words(self._publish_queue, word_tile_ids)
            self._score_card.add_staged_guess(guess)
            events.trigger("game.stage_guess", self._score_card.calculate_score(guess), guess)
            self._update_rack_display(len(guess_tiles), len(guess))
        elif move_tiles:
            self._update_rack_display(0, len(guess))

    async def guess_word_keyboard(self, guess):
        await self.guess_tiles(self._player_rack.letters_to_ids(guess), True)

    def _update_next_tile(self, next_tile):
        events.trigger("game.next_tile", next_tile)

    def _update_previous_guesses(self):
        events.trigger("input.previous_guesses",
            self._score_card.get_previous_guesses())

    def _update_remaining_previous_guesses(self):
        events.trigger("input.remaining_previous_guesses", self._score_card.get_remaining_previous_guesses())

    def _update_rack_display(self, highlight_length, guess_length):
        events.trigger("rack.update_rack", self._player_rack.get_tiles(), highlight_length, guess_length)

