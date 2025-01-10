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

MQTT_BROKER = 'localhost'
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

BUNDLE_TEMP_DIR = "."

class App:
    def __init__(self, client):
        def make_guess_tiles_callback(the_app):
            async def guess_tiles_callback(guess):
                await the_app.guess_tiles(guess)
            return guess_tiles_callback

        self._client = client
        self._dictionary = Dictionary(tiles.MIN_LETTERS, tiles.MAX_LETTERS, open=my_open)
        self._dictionary.read(f"{BUNDLE_TEMP_DIR}/sowpods.txt")

        self._player_rack = tiles.Rack('?' * tiles.MAX_LETTERS)
        self._score_card = ScoreCard(self._player_rack, self._dictionary)
        cubes_to_game.set_guess_tiles_callback(make_guess_tiles_callback(self))
        self._running = False

    async def start(self):
        self._player_rack = self._dictionary.get_rack()
        self._update_next_tile(self._player_rack.next_letter())
        self._score_card = ScoreCard(self._player_rack, self._dictionary)
        await self.load_rack()
        self._update_rack()
        await self._update_score()
        await self._update_previous_guesses()
        await self._update_remaining_previous_guesses()
        self._score_card.start()
        self._running = True

    def stop(self):
        self._player_rack = tiles.Rack('?' * tiles.MAX_LETTERS)
        self._score_card.stop()
        self._running = False

    async def load_rack(self, ):
        await cubes_to_game.load_rack(self._client, self._player_rack.get_tiles())

    async def accept_new_letter(self, next_letter, position):
        changed_tile = self._player_rack.replace_letter(next_letter, position)
        self._score_card.update_previous_guesses()
        await cubes_to_game.accept_new_letter(self._client, next_letter, position)

        await self._update_previous_guesses()
        await self._update_remaining_previous_guesses()
        self._update_rack()
        self._update_next_tile(self._player_rack.next_letter())

    async def guess_tiles(self, word_tile_ids):
        logger.info(f"guess_tiles: {word_tile_ids}")
        if not self._running:
            logger.info(f"not running, bailing")
            return
        guess = ""
        for word_tile_id in word_tile_ids:
            for rack_tile in self._player_rack.get_tiles():
                if rack_tile.id == word_tile_id:
                    guess += rack_tile.letter
                    break
        score = self._score_card.guess_word(guess)
        await self._update_score()
        if score:
            await self._update_previous_guesses()
            self._update_rack()
            await cubes_to_game.flash_good_words(self._client, word_tile_ids)

        logger.info(f"guess_tiles: {score}")

    async def guess_word_keyboard(self, guess):
        word_tile_ids = ""
        rack_tiles = self._player_rack.get_tiles.copy()
        for letter in guess:
            for rack_tile in rack_tiles:
                if rack_tile.letter == letter:
                    rack_tiles.remove(rack_tile)
                    word_tile_ids += rack_tile.id
                    break

        await self.guess_tiles(word_tile_ids)

    def _update_next_tile(self, next_tile):
        events.trigger("game.next_tile", next_tile)

    async def _update_previous_guesses(self):
        events.trigger("input.previous_guesses", self._score_card.get_previous_guesses())

    async def _update_remaining_previous_guesses(self):
        events.trigger("input.remaining_previous_guesses", self._score_card.get_remaining_previous_guesses())

    def _update_rack(self):
        events.trigger("rack.change_rack", self._player_rack.letters())

    async def _update_score(self):
        events.trigger("game.current_score", self._score_card.current_score, self._score_card.last_guess)

