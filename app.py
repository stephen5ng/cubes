import asyncio
from collections import Counter
from datetime import datetime
from functools import wraps
import logging
from typing import Any, Callable, Coroutine

import cubes_to_game
from config import MAX_PLAYERS, MQTT_CLIENT_ID, MQTT_CLIENT_PORT
from dictionary import Dictionary
from pygameasync import events
import tiles
from scorecard import ScoreCard

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

        def make_start_game_callback(the_app: App) -> Callable[[bool],  Coroutine[Any, Any, None]]:
            async def start_game_callback(force: bool) -> None:
                if force or not the_app._running:
                    events.trigger("game.start")
            return start_game_callback

        self._dictionary = dictionary
        self._publish_queue = publish_queue
        self._last_guess: list[str] = []
        self._player_racks = [tiles.Rack('?' * tiles.MAX_LETTERS) for _ in range(MAX_PLAYERS)]
        self._score_card = ScoreCard(self._player_racks[0], self._dictionary)
        self._player_count = 1
        cubes_to_game.set_guess_tiles_callback(make_guess_tiles_callback(self))
        cubes_to_game.set_start_game_callback(make_start_game_callback(self))
        self._running = False

    async def start(self) -> None:
        the_rack = self._dictionary.get_rack()
        for player in range(MAX_PLAYERS):
            self._player_racks[player].set_tiles(the_rack.get_tiles())
        
        self._update_next_tile(self._player_racks[0].next_letter())
        self._score_card = ScoreCard(self._player_racks[0], self._dictionary)
        await self.load_rack()
        for player in range(MAX_PLAYERS):
            self._update_rack_display(0, 0, player)
        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        for player in range(self._player_count):
            await cubes_to_game.guess_last_tiles(self._publish_queue, player)
        self._running = True

    async def stop(self) -> None:
        for player in range(MAX_PLAYERS):
            self._player_racks[player] = tiles.Rack(' ' * tiles.MAX_LETTERS)
        await self.load_rack()
        self._running = False

    async def load_rack(self) -> None:
        for player in range(MAX_PLAYERS):
            await cubes_to_game.load_rack(self._publish_queue, self._player_racks[player].get_tiles(), player)

    async def accept_new_letter(self, next_letter: str, position: int) -> None:
        if self._player_count > 1:
            # Replace the tile in the rack that was hit, then replace that same tile in the other rack.
            hit_rack, other_rack, position_offset = (0, 1, 3) if position < 3 else (1, 0, -3)
            
            changed_tile = self._player_racks[hit_rack].replace_letter(next_letter, position + position_offset)
            other_position = self._player_racks[other_rack].id_to_position(changed_tile.id)
            self._player_racks[other_rack].replace_letter(next_letter, other_position)
        else:
            changed_tile = self._player_racks[0].replace_letter(next_letter, position)

        self._score_card.update_previous_guesses()
        for player in range(self._player_count):
            await cubes_to_game.accept_new_letter(self._publish_queue, next_letter, changed_tile.id, player)

        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        for player in range(self._player_count):
            events.trigger("rack.update_letter", changed_tile, player)
        self._update_next_tile(self._player_racks[0].next_letter())
        if changed_tile.id in self._last_guess:
            for player in range(self._player_count):
                await self.guess_tiles(self._last_guess, False, player)

    async def letter_lock(self, position: int, locked_on: bool) -> None:
        for rack in self._player_racks:
            await cubes_to_game.letter_lock(self._publish_queue, locked_on, rack.position_to_id(position))

    def add_guess(self, guess: str, player: int) -> None:
        self._score_card.add_guess(guess, player)
        events.trigger("input.add_guess", self._score_card.get_previous_guesses(), guess, player)

    async def guess_tiles(self, word_tile_ids: list[str], move_tiles: bool, player: int) -> None:
        self._last_guess = word_tile_ids
        logger.info(f"guess_tiles: word_tile_ids {word_tile_ids}")
        if not self._running:
            logger.info(f"not running, bailing")
            return
        guess = self._player_racks[player].ids_to_letters(word_tile_ids)
        guess_tiles = self._player_racks[player].ids_to_tiles(word_tile_ids)

        tiles_dirty = False
        good_guess_highlight = 0
        if move_tiles:
            remaining_tiles = self._player_racks[player].get_tiles().copy()
            for guess_tile in guess_tiles:
                remaining_tiles.remove(guess_tile)
            if player == 0:
                self._player_racks[player].set_tiles(guess_tiles + remaining_tiles)
            else:
                self._player_racks[player].set_tiles(remaining_tiles + guess_tiles)
            tiles_dirty = True

        if self._score_card.is_old_guess(guess):
            events.trigger("game.old_guess", guess, player)
            await cubes_to_game.old_guess(self._publish_queue, word_tile_ids, player)
            tiles_dirty = True
        elif self._score_card.is_good_guess(guess):
            await cubes_to_game.good_guess(self._publish_queue, word_tile_ids, player)
            self._score_card.add_staged_guess(guess)
            events.trigger("game.stage_guess", 
                           self._score_card.calculate_score(guess), guess, player)
            good_guess_highlight = len(guess_tiles)
            tiles_dirty = True
        else:
            events.trigger("game.bad_guess", player)
            await cubes_to_game.bad_guess(self._publish_queue, word_tile_ids, player)

        if tiles_dirty:
            self._update_rack_display(good_guess_highlight, len(guess), player)

    async def guess_word_keyboard(self, guess: str, player: int) -> None:
        # not sure why this is here.
        # if MAX_PLAYERS == 1 and player > 0:
        #     return
        await cubes_to_game.guess_tiles(self._publish_queue,
            [self._player_racks[player].letters_to_ids(guess)], player)

    def _update_next_tile(self, next_tile: str) -> None:
        events.trigger("game.next_tile", next_tile)

    def _update_previous_guesses(self) -> None:
        events.trigger("input.update_previous_guesses",
            self._score_card.get_previous_guesses())

    def _update_remaining_previous_guesses(self) -> None:
        events.trigger("input.remaining_previous_guesses", self._score_card.get_remaining_previous_guesses())

    def _update_rack_display(self, highlight_length: int, guess_length: int, player: int):
        events.trigger("rack.update_rack", self._player_racks[player].get_tiles(), highlight_length, guess_length, player)

