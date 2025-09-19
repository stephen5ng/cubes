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
import pygame
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
            async def guess_tiles_callback(guess: list[str], move_tiles: bool, player: int, now_ms: int) -> None:
                await the_app.guess_tiles(guess, move_tiles, player, now_ms)
            return guess_tiles_callback

        def make_start_game_callback(the_app: App) -> Callable[[bool, int, int],  Coroutine[Any, Any, None]]:
            async def start_game_callback(force: bool, now_ms: int, player: int) -> None:
                if force or not the_app._running:
                    print(f"starting from callback for player {player}")
                    events.trigger("game.start_player", now_ms, player)
            return start_game_callback

        self._dictionary = dictionary
        self._publish_queue = publish_queue
        self._last_guess: list[str] = []
        self._player_racks = [tiles.Rack('?' * tiles.MAX_LETTERS) for _ in range(MAX_PLAYERS)]
        self._score_card = ScoreCard(self._player_racks[0], self._dictionary)
        self._player_count = 1
        # Map logical players to physical cube sets
        self._player_to_cube_set = {0: 0, 1: 1}  # Default: player 0 → cube set 0, player 1 → cube set 1
        self._game_logger = None  # Will be set by the game
        cubes_to_game.set_guess_tiles_callback(make_guess_tiles_callback(self))
        cubes_to_game.set_start_game_callback(make_start_game_callback(self))
        self._running = False

    @property
    def player_count(self) -> int:
        return self._player_count

    @player_count.setter
    def player_count(self, value: int) -> None:
        self._player_count = value

    def set_game_logger(self, game_logger) -> None:
        """Set the game logger for MQTT event logging."""
        self._game_logger = game_logger

    def get_game_logger(self):
        """Get the game logger for MQTT event logging."""
        return self._game_logger

    def _determine_active_cube_sets(self) -> set[int]:
        """Determine which cube sets are currently active (have ABC assignments or started games)."""
        active_cube_sets = set()

        # Add cube sets with ABC assignments
        active_cube_sets.update(cubes_to_game.abc_manager.player_abc_cubes.keys())

        # Add cube sets with started games
        active_cube_sets.update(cubes_to_game._game_started_players)

        return active_cube_sets

    def _update_player_to_cube_set_mapping(self) -> None:
        """Update the player-to-cube-set mapping based on active cube sets."""
        active_cube_sets = self._determine_active_cube_sets()

        if not active_cube_sets:
            # No active cube sets, keep default mapping
            return

        # For single player mode, map player 0 to the first active cube set
        if self._player_count == 1:
            first_active = min(active_cube_sets)
            self._player_to_cube_set[0] = first_active
        else:
            # For multi-player, maintain current mapping or assign in order
            active_list = sorted(active_cube_sets)
            for i in range(min(self._player_count, len(active_list))):
                self._player_to_cube_set[i] = active_list[i]

    def set_word_logger(self, word_logger) -> None:
        """Set the word logger for new word formation logging."""
        self._word_logger = word_logger

    async def start(self, now_ms: int) -> None:
        print(">>>>>>>> app.STARTING")
        self._running = True
        # Set game running state for cube border logic
        cubes_to_game.set_game_running(True)
        the_rack = self._dictionary.get_rack()
        for player in range(MAX_PLAYERS):
            self._player_racks[player].set_tiles(the_rack.get_tiles())
        
        self._update_next_tile(self._player_racks[0].next_letter())
        self._score_card = ScoreCard(self._player_racks[0], self._dictionary)
        
        # Remove participating players from ABC tracking (their cubes will get game letters)
        for player in range(cubes_to_game.MAX_PLAYERS):
            if cubes_to_game.has_player_started_game(player) and player in cubes_to_game.abc_manager.player_abc_cubes:
                del cubes_to_game.abc_manager.player_abc_cubes[player]
        
        # Clear ABC cubes for any remaining players (non-participants)
        await cubes_to_game.clear_remaining_abc_cubes(self._publish_queue, now_ms)
        
        await self.load_rack(now_ms)
        for player in range(MAX_PLAYERS):
            self._update_rack_display(0, 0, player)
        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        for player in range(self._player_count):
            await cubes_to_game.guess_last_tiles(self._publish_queue, player, now_ms)
        print(">>>>>>>> app.STARTED")

    async def stop(self, now_ms: int) -> None:
        for player in range(MAX_PLAYERS):
            self._player_racks[player] = tiles.Rack(' ' * tiles.MAX_LETTERS)
        await self.load_rack(now_ms)
        self._running = False
        # Set game ended state
        cubes_to_game.set_game_end_time(now_ms)
        # Ensure all borders are cleared on every cube at game end
        await cubes_to_game.clear_all_borders(self._publish_queue, now_ms)
        # Note: ABC sequence will be activated automatically

    async def load_rack(self, now_ms: int) -> None:
        # Only load letters for players who have actually started their games
        for player in range(MAX_PLAYERS):
            if cubes_to_game.has_player_started_game(player):
                await cubes_to_game.load_rack(self._publish_queue, self._player_racks[player].get_tiles(), player, now_ms)
            else:
                logging.info(f"LOAD RACK: Skipping player {player} - game not started")

    async def accept_new_letter(self, next_letter: str, position: int, now_ms: int) -> None:
        if self._player_count > 1:
            # Replace the tile in the rack that was hit, then replace that same tile in the other rack.
            hit_rack, other_rack, position_offset = (0, 1, 3) if position < 3 else (1, 0, -3)
            
            changed_tile = self._player_racks[hit_rack].replace_letter(next_letter, position + position_offset)
            other_position = self._player_racks[other_rack].id_to_position(changed_tile.id)
            self._player_racks[other_rack].replace_letter(next_letter, other_position)
        else:
            changed_tile = self._player_racks[0].replace_letter(next_letter, position)

        self._score_card.update_previous_guesses()
        # Update player-to-cube-set mapping before sending letters
        self._update_player_to_cube_set_mapping()
        for player in range(self._player_count):
            cube_set_id = self._player_to_cube_set.get(player)
            if cube_set_id is not None:
                await cubes_to_game.accept_new_letter(self._publish_queue, next_letter, changed_tile.id, cube_set_id, now_ms)

        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        for player in range(self._player_count):
            events.trigger("rack.update_letter", changed_tile, player, now_ms)
        self._update_next_tile(self._player_racks[0].next_letter())
        if changed_tile.id in self._last_guess:
            for player in range(self._player_count):
                await self.guess_tiles(self._last_guess, False, player, now_ms)

    async def letter_lock(self, position: int | None, now_ms: int) -> bool:
        lock_change = False
        # Update player-to-cube-set mapping before sending locks
        self._update_player_to_cube_set_mapping()
        for player in range(self._player_count):
            cube_set_id = self._player_to_cube_set.get(player)
            if cube_set_id is not None:
                lock_change |= await cubes_to_game.letter_lock(self._publish_queue,
                    cube_set_id,
                    self._player_racks[player].position_to_id(position) if position else None,
                    now_ms)
        return lock_change

    def add_guess(self, guess: str, player: int) -> None:
        self._score_card.add_guess(guess, player)
        events.trigger("input.add_guess", self._score_card.get_previous_guesses(), guess, player, pygame.time.get_ticks())

    async def guess_tiles(self, word_tile_ids: list[str], move_tiles: bool, player: int, now_ms: int) -> None:
        self._last_guess = word_tile_ids
        logger.info(f"guess_tiles: word_tile_ids {word_tile_ids}")
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
            events.trigger("game.old_guess", guess, player, pygame.time.get_ticks())
            await cubes_to_game.old_guess(self._publish_queue, word_tile_ids, player)
            tiles_dirty = True
        elif self._score_card.is_good_guess(guess):
            await cubes_to_game.good_guess(self._publish_queue, word_tile_ids, player, now_ms)
            self._score_card.add_staged_guess(guess)
            score = self._score_card.calculate_score(guess)
            events.trigger("game.stage_guess", score, guess, player, now_ms)
            self._word_logger.log_word_formed(guess, player, score, now_ms)
            good_guess_highlight = len(guess_tiles)
            tiles_dirty = True
        else:
            events.trigger("game.bad_guess", player)
            await cubes_to_game.bad_guess(self._publish_queue, word_tile_ids, player)

        if tiles_dirty:
            self._update_rack_display(good_guess_highlight, len(guess), player)

    async def guess_word_keyboard(self, guess: str, player: int, now_ms: int) -> None:
        # not sure why this is here.
        # if MAX_PLAYERS == 1 and player > 0:
        #     return
        await cubes_to_game.guess_tiles(self._publish_queue,
            [self._player_racks[player].letters_to_ids(guess)], player, now_ms)

    def _update_next_tile(self, next_tile: str) -> None:
        events.trigger("game.next_tile", next_tile, pygame.time.get_ticks())

    def _update_previous_guesses(self) -> None:
        events.trigger("input.update_previous_guesses",
            self._score_card.get_previous_guesses(), pygame.time.get_ticks())

    def _update_remaining_previous_guesses(self) -> None:
        events.trigger("input.remaining_previous_guesses", 
                       self._score_card.get_remaining_previous_guesses(),
                       pygame.time.get_ticks())

    def _update_rack_display(self, highlight_length: int, guess_length: int, player: int):
        events.trigger("rack.update_rack", 
                       self._player_racks[player].get_tiles(),
                       highlight_length,
                       guess_length,
                       player,
                       pygame.time.get_ticks())
