import asyncio
from collections import Counter
from datetime import datetime
from functools import wraps
import logging
from typing import Any, Callable, Coroutine

from hardware import cubes_to_game
from hardware.cubes_to_game import state as ctg_state
from config import game_config
from core.dictionary import Dictionary
from utils.pygameasync import events
import pygame
from core import tiles
from core.scorecard import ScoreCard
from events.game_events import (
    GameStartPlayerEvent,
    GameStageGuessEvent,
    GameOldGuessEvent,
    GameBadGuessEvent,
    GameNextTileEvent,
    RackUpdateRackEvent,
    RackUpdateLetterEvent,
    InputAddGuessEvent,
    InputUpdatePreviousGuessesEvent,
    InputRemainingPreviousGuessesEvent,
)
from core.player_mapping import calculate_player_mapping

logger = logging.getLogger("app:"+__name__)

class App:
    def __init__(self, publish_queue: asyncio.Queue, dictionary: Dictionary, hardware_interface=None) -> None:
        def make_guess_tiles_callback(the_app: App) -> Callable[[list[str], bool, int],  Coroutine[Any, Any, None]]:
            async def guess_tiles_callback(guess: list[str], move_tiles: bool, player: int, now_ms: int) -> None:
                await the_app.guess_tiles(guess, move_tiles, player, now_ms)
            return guess_tiles_callback

        def make_start_game_callback(the_app: App) -> Callable[[bool, int, int],  Coroutine[Any, Any, None]]:
            async def start_game_callback(force: bool, now_ms: int, player: int) -> None:
                if force or not the_app._running:
                    print(f"starting from callback for player {player}")
                    events.trigger(GameStartPlayerEvent(now_ms, player))
            return start_game_callback

        self._dictionary = dictionary
        self._publish_queue = publish_queue
        # Inject hardware interface or default to global module
        self._hardware = hardware_interface or cubes_to_game
        self._last_guess: list[str] = []
        self._player_racks = [tiles.Rack('?' * game_config.MAX_LETTERS) for _ in range(game_config.MAX_PLAYERS)]
        self._score_card = ScoreCard(self._player_racks[0], self._dictionary)
        self._player_count = 1
        # Map logical players to physical cube sets
        self._player_to_cube_set = {0: 0, 1: 1}  # Default: player 0 → cube set 0, player 1 → cube set 1
        self._game_logger = None  # Will be set by the game
        
        # Callbacks still go to global module for now as main.py/coordination init sets them there
        # but we could channel them through hardware interface if we fully wrapped it.
        # For now, just setting them on the global module is fine as they are static slots.
        if self._hardware == cubes_to_game:
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

    def _set_player_to_cube_set_mapping(self) -> None:
        """Set the player-to-cube-set mapping once when game starts."""
        # Get cube set IDs from ABC completion
        started_cube_sets = self._hardware.get_started_cube_sets()

        # Reset and populate player started state
        self._hardware.reset_player_started_state()

        # Calculate mapping using pure logic
        new_mapping = calculate_player_mapping(started_cube_sets)
        self._player_to_cube_set.update(new_mapping)

        if not started_cube_sets:
            # Default/Keyboard mode: Mark player 0 as started
            self._hardware.add_player_started(0)
            return

        # Mark all mapped players as started in hardware
        for player_id in new_mapping:
             self._hardware.add_player_started(player_id)

    def set_word_logger(self, word_logger) -> None:
        """Set the word logger for new word formation logging."""
        self._word_logger = word_logger

    async def start(self, now_ms: int) -> None:
        print(">>>>>>>> app.STARTING")
        self._running = True
        # Set game running state for cube border logic
        self._hardware.set_game_running(True)
        the_rack = self._dictionary.get_rack()
        for player in range(game_config.MAX_PLAYERS):
            self._player_racks[player].set_tiles(the_rack.get_tiles())
            self._player_racks[player].refresh_next_letter()
        
        self._update_next_tile(self._player_racks[0].next_letter())
        self._score_card = ScoreCard(self._player_racks[0], self._dictionary)
        
        # Remove participating players from ABC tracking (their cubes will get game letters)
        for player in range(game_config.MAX_PLAYERS):
            if self._hardware.has_player_started_game(player) and player in ctg_state.abc_manager.player_abc_cubes:
                del ctg_state.abc_manager.player_abc_cubes[player]
        
        # Clear ABC cubes for any remaining players (non-participants)
        await self._hardware.clear_remaining_abc_cubes(self._publish_queue, now_ms)

        # Set player-to-cube-set mapping once for this game session
        self._set_player_to_cube_set_mapping()

        await self.load_rack(now_ms)
        for player in range(game_config.MAX_PLAYERS):
            self._update_rack_display(0, 0, player)
        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        for player in range(self._player_count):
            cube_set_id = self._player_to_cube_set[player]
            await self._hardware.guess_last_tiles(self._publish_queue, cube_set_id, player, now_ms)
        print(">>>>>>>> app.STARTED")

    async def stop(self, now_ms: int) -> None:
        for player in range(game_config.MAX_PLAYERS):
            self._player_racks[player] = tiles.Rack(' ' * game_config.MAX_LETTERS)
        await self.load_rack(now_ms)
        self._running = False
        # Set game ended state
        self._hardware.set_game_end_time(now_ms)
        # Unlock all letters when game ends
        await self._hardware.unlock_all_letters(self._publish_queue, now_ms)
        # Ensure all borders are cleared on every cube at game end
        await self._hardware.clear_all_borders(self._publish_queue, now_ms)
        # Note: ABC sequence will be activated automatically

    async def load_rack(self, now_ms: int) -> None:
        # Only load letters for players who have actually started their games
        for player in range(game_config.MAX_PLAYERS):
            if self._hardware.has_player_started_game(player):
                cube_set_id = self._player_to_cube_set[player]
                await self._hardware.load_rack(self._publish_queue, self._player_racks[player].get_tiles(), cube_set_id, player, now_ms)
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
        for player in range(self._player_count):
            cube_set_id = self._player_to_cube_set[player]
            await self._hardware.accept_new_letter(self._publish_queue, next_letter,
                                                  changed_tile.id, cube_set_id, now_ms)

        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        for player in range(self._player_count):
            events.trigger(RackUpdateLetterEvent(changed_tile, player, now_ms))
        self._update_next_tile(self._player_racks[0].next_letter())
        if changed_tile.id in self._last_guess:
            for player in range(self._player_count):
                await self.guess_tiles(self._last_guess, False, player, now_ms)

    async def letter_lock(self, position: int, locked: bool, now_ms: int) -> bool:
        position_offset = 0
        hit_rack = 0
        if self._player_count > 1:
            hit_rack, position_offset = (0, 3) if position < 3 else (1, -3)

        locked_tile_id = self._player_racks[hit_rack].position_to_id(position + position_offset)

        lock_changed = False
        for player in range(self._player_count):
            cube_set_id = self._player_to_cube_set[player]
            lock_changed |= await cubes_to_game.letter_lock(self._publish_queue, cube_set_id,
                                            locked_tile_id if locked else None, now_ms)
        return lock_changed

    def add_guess(self, guess: str, player: int) -> None:
        self._score_card.add_guess(guess, player)
        events.trigger(InputAddGuessEvent(self._score_card.get_previous_guesses(), guess, player, pygame.time.get_ticks()))

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

        cube_set_id = self._player_to_cube_set[player]
        if self._score_card.is_old_guess(guess):
            events.trigger(GameOldGuessEvent(guess, player, pygame.time.get_ticks()))
            await cubes_to_game.old_guess(self._publish_queue, word_tile_ids, cube_set_id, player)
            tiles_dirty = True
        elif self._score_card.is_good_guess(guess):
            await cubes_to_game.good_guess(self._publish_queue, word_tile_ids, cube_set_id, player, now_ms)
            self._score_card.add_staged_guess(guess)
            score = self._score_card.calculate_score(guess)
            events.trigger(GameStageGuessEvent(score, guess, player, now_ms))
            self._word_logger.log_word_formed(guess, player, score, now_ms)
            good_guess_highlight = len(guess_tiles)
            tiles_dirty = True
        else:
            events.trigger(GameBadGuessEvent(player))
            await cubes_to_game.bad_guess(self._publish_queue, word_tile_ids, cube_set_id, player)

        if tiles_dirty:
            self._update_rack_display(good_guess_highlight, len(guess), player)

    async def guess_word_keyboard(self, guess: str, player: int, now_ms: int) -> None:
        # not sure why this is here.
        # if MAX_PLAYERS == 1 and player > 0:
        #     return
        cube_set_id = self._player_to_cube_set[player]
        await cubes_to_game.guess_tiles(self._publish_queue,
            [self._player_racks[player].letters_to_ids(guess)], cube_set_id, player, now_ms)

    def _update_next_tile(self, next_tile: str) -> None:
        events.trigger(GameNextTileEvent(next_tile, pygame.time.get_ticks()))

    def _update_previous_guesses(self) -> None:
        events.trigger(InputUpdatePreviousGuessesEvent(
            self._score_card.get_previous_guesses(), pygame.time.get_ticks()))

    def _update_remaining_previous_guesses(self) -> None:
        events.trigger(InputRemainingPreviousGuessesEvent(
                       self._score_card.get_remaining_previous_guesses(),
                       pygame.time.get_ticks()))

    def _update_rack_display(self, highlight_length: int, guess_length: int, player: int):
        events.trigger(RackUpdateRackEvent(
                       self._player_racks[player].get_tiles(),
                       highlight_length,
                       guess_length,
                       player,
                       pygame.time.get_ticks()))
