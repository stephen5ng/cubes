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
from typing import Any, Callable, Coroutine
import psutil
import signal

import cubes_to_game
from dictionary import Dictionary
from pygameasync import events
import tiles
from scorecard import ScoreCard

MQTT_CLIENT_ID = 'game-server'
MQTT_CLIENT_PORT = 1883

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
    def __init__(self, publish_queue: asyncio.Queue, dictionary: Dictionary) -> None:
        def make_guess_tiles_callback(the_app: App) -> Callable[[list[str], bool, int],  Coroutine[Any, Any, None]]:
            async def guess_tiles_callback(guess: list[str], move_tiles: bool, player: int) -> None:
                await the_app.guess_tiles(guess, move_tiles, player)
            return guess_tiles_callback

        self._dictionary = dictionary
        self._publish_queue = publish_queue
        self._last_guess: list[str] = []
        self._player_rack = tiles.Rack('?' * tiles.MAX_LETTERS)
        self._score_card = ScoreCard(self._player_rack, self._dictionary)
        cubes_to_game.set_guess_tiles_callback(make_guess_tiles_callback(self))
        self._running = False

    async def start(self) -> None:
        self._player_rack = self._dictionary.get_rack()
        self._update_next_tile(self._player_rack.next_letter())
        self._score_card = ScoreCard(self._player_rack, self._dictionary)
        await self.load_rack()
        self._update_rack_display(0, 0)
        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        # TODO(sng): needs to check both rack sets.
        await cubes_to_game.guess_last_tiles(self._publish_queue, 0)
        self._running = True

    async def stop(self) -> None:
        self._player_rack = tiles.Rack(' ' * tiles.MAX_LETTERS)
        await self.load_rack()
        self._running = False

    async def load_rack(self) -> None:
        await cubes_to_game.load_rack(self._publish_queue, self._player_rack.get_tiles())

    async def accept_new_letter(self, next_letter: str, position: int) -> None:
        changed_tile = self._player_rack.replace_letter(next_letter, position)

        self._score_card.update_previous_guesses()
        await cubes_to_game.accept_new_letter(self._publish_queue, next_letter, changed_tile.id)

        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        events.trigger("rack.update_letter", changed_tile, position)
        self._update_next_tile(self._player_rack.next_letter())
        if changed_tile.id in self._last_guess:
            # TODO(sng): needs to check both rack sets.
            await self.guess_tiles(self._last_guess, False, 0)

    def add_guess(self, guess: str, player: int) -> None:
        self._score_card.add_guess(guess, player)
        events.trigger("input.add_guess",
            self._score_card.get_previous_guesses(), guess, player)

        self._update_previous_guesses()

    async def guess_tiles(self, word_tile_ids: list[str], move_tiles: bool, player: int) -> None:
        self._last_guess = word_tile_ids
        logger.info(f"guess_tiles: word_tile_ids {word_tile_ids}")
        if not self._running:
            logger.info(f"not running, bailing")
            return
        guess = self._player_rack.ids_to_letters(word_tile_ids)
        guess_tiles = self._player_rack.ids_to_tiles(word_tile_ids)

        tiles_dirty = False
        good_guess_highlight = 0
        if move_tiles:
            remaining_tiles = self._player_rack.get_tiles().copy()
            for guess_tile in guess_tiles:
                remaining_tiles.remove(guess_tile)
            self._player_rack.set_tiles(guess_tiles + remaining_tiles)
            tiles_dirty = True

        if self._score_card.is_old_guess(guess):
            events.trigger("game.old_guess", guess)
            await cubes_to_game.old_guess(self._publish_queue, word_tile_ids)
            tiles_dirty = True
        elif self._score_card.is_good_guess(guess):
            await cubes_to_game.good_guess(self._publish_queue, word_tile_ids)
            self._score_card.add_staged_guess(guess)
            events.trigger("game.stage_guess", 
                           self._score_card.calculate_score(guess), guess, player)
            good_guess_highlight = len(guess_tiles)
            tiles_dirty = True
        else:
            events.trigger("game.bad_guess")
            await cubes_to_game.bad_guess(self._publish_queue, word_tile_ids)

        if tiles_dirty:
            self._update_rack_display(good_guess_highlight, len(guess))

    async def guess_word_keyboard(self, guess: str, player: int) -> None:
        await cubes_to_game.guess_tiles(self._publish_queue,
            [self._player_rack.letters_to_ids(guess)], player)

    def _update_next_tile(self, next_tile: str) -> None:
        events.trigger("game.next_tile", next_tile)

    def _update_previous_guesses(self) -> None:
        events.trigger("input.update_previous_guesses",
            self._score_card.get_previous_guesses())

    def _update_remaining_previous_guesses(self) -> None:
        events.trigger("input.remaining_previous_guesses", self._score_card.get_remaining_previous_guesses())

    def _update_rack_display(self, highlight_length: int, guess_length: int):
        events.trigger("rack.update_rack", self._player_rack.get_tiles(), highlight_length, guess_length)

