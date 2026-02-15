import asyncio
from collections import Counter
from datetime import datetime
from functools import wraps
import logging
from typing import Any, Callable, Coroutine, Optional

from game.time_provider import TimeProvider, SystemTimeProvider
from hardware.interface import HardwareInterface
from config import game_config
from core.dictionary import Dictionary
from utils.pygameasync import events
import pygame
from core import tiles
from core.scorecard import ScoreCard
from game_logging.game_loggers import OutputLogger
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

from core.rack_manager import RackManager
from core.tile_generator import TileGenerator

class App:
    def __init__(self, publish_queue: asyncio.Queue, dictionary: Dictionary, hardware_interface: HardwareInterface, time_provider: Optional[TimeProvider] = None) -> None:
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

        def make_remove_highlight_callback(the_app: App) -> Callable[[list[str], int],  Coroutine[Any, Any, None]]:
            async def remove_highlight_callback(word_tile_ids: list[str], player: int) -> None:
                await the_app.remove_highlight(word_tile_ids, player)
            return remove_highlight_callback

        self._dictionary = dictionary
        self._publish_queue = publish_queue
        self.hardware = hardware_interface
        self._time = time_provider or SystemTimeProvider()
        self._last_guess: list[str] = []
        
        tile_generator = TileGenerator()
        self.rack_manager = RackManager(dictionary, tile_generator)
        
        self._score_card = ScoreCard(self.rack_manager.get_rack(0), self._dictionary)
        self._player_count = 1
        # Map logical players to physical cube sets
        self._player_to_cube_set = {0: 0, 1: 1}  # Default: player 0 → cube set 0, player 1 → cube set 1
        self._game_logger = None  # Will be set by the game
        self._word_logger = OutputLogger(None)  # No-op logger until set by the game
        
        self.hardware.set_guess_tiles_callback(make_guess_tiles_callback(self))
        self.hardware.set_remove_highlight_callback(make_remove_highlight_callback(self))
        self.hardware.set_start_game_callback(make_start_game_callback(self))
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
        started_cube_sets = self.hardware.get_started_cube_sets()

        # Reset and populate player started state
        self.hardware.reset_player_started_state()

        # Calculate mapping using pure logic
        new_mapping = calculate_player_mapping(started_cube_sets)
        self._player_to_cube_set.update(new_mapping)

        if not started_cube_sets:
            # Default/Keyboard mode: Mark player 0 as started
            self.hardware.add_player_started(0)
            return

        # Mark all mapped players as started in hardware
        for player_id in new_mapping:
             self.hardware.add_player_started(player_id)

    def set_word_logger(self, word_logger) -> None:
        """Set the word logger for new word formation logging."""
        self._word_logger = word_logger

    def get_player_border_color(self, player: int) -> Optional[str]:
        """Get border color for a player's cube set.

        Args:
            player: Player ID (0 or 1)

        Returns:
            Hex color string or None

        Example:
            color = app.get_player_border_color(0)
            assert color == "0x07E0"  # green for good guess
        """
        cube_set = self._player_to_cube_set.get(player, player)
        return self.hardware.get_cube_set_border_color(cube_set)

    def get_player_cube_set_mapping(self, player: int) -> int:
        """Get the cube set assigned to a player.

        Args:
            player: Player ID (0 or 1)

        Returns:
            Cube set ID (0 for cubes 1-6, 1 for cubes 11-16)

        Example:
            cube_set = app.get_player_cube_set_mapping(0)
            assert cube_set == 0
        """
        return self._player_to_cube_set.get(player, player)

    def get_all_player_mappings(self) -> dict[int, int]:
        """Get all player-to-cube-set mappings.

        Returns:
            Dictionary mapping player IDs to cube set IDs

        Example:
            mappings = app.get_all_player_mappings()
            assert mappings == {0: 0, 1: 1}
        """
        return self._player_to_cube_set.copy()

    def _initialize_racks_for_fair_play(self) -> None:
        """Initialize racks using the RackManager."""
        self.rack_manager.initialize_racks_for_fair_play()

    async def start(self, now_ms: int) -> None:
        print(">>>>>>>> app.STARTING")
        self._running = True
        # Set game running state for cube border logic
        self.hardware.set_game_running(True)
        self._initialize_racks_for_fair_play()

        self._update_next_tile(self.rack_manager.get_rack(0).next_letter())
        self._score_card = ScoreCard(self.rack_manager.get_rack(0), self._dictionary)
        
        # Set player-to-cube-set mapping once for this game session
        self._set_player_to_cube_set_mapping()

        # Remove participating players from ABC tracking (their cubes will get game letters)
        for player in range(game_config.MAX_PLAYERS):
            if self.hardware.has_player_started_game(player):
                self.hardware.remove_player_from_abc_tracking(player)
        
        # Clear ABC cubes for any remaining players (non-participants)
        await self.hardware.clear_remaining_abc_cubes(self._publish_queue, now_ms)

        await self.load_rack(now_ms)
        for player in range(game_config.MAX_PLAYERS):
            self._update_rack_display(0, 0, player, None)
        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        for player in range(self._player_count):
            cube_set_id = self._player_to_cube_set[player]
            await self.hardware.guess_last_tiles(self._publish_queue, cube_set_id, player, now_ms)
        print(">>>>>>>> app.STARTED")

    async def stop(self, now_ms: int, min_win_score: int) -> None:
        # Clear hardware cubes - we do this directly without clearing our logical RackManager,
        # so that post-game UI effects (like melting) can still access the final game state.
        await self.hardware.clear_all_letters(self._publish_queue, now_ms)

        self._running = False
        # Set game ended state
        self.hardware.set_game_end_time(now_ms, min_win_score)
        # Unlock all letters when game ends
        await self.hardware.unlock_all_letters(self._publish_queue, now_ms)
        # Ensure all borders are cleared on every cube at game end
        await self.hardware.clear_all_borders(self._publish_queue, now_ms)
        # Note: ABC sequence will be activated automatically

    async def load_rack(self, now_ms: int) -> None:
        # Only load letters for players who have actually started their games
        for player in range(game_config.MAX_PLAYERS):
            if self.hardware.has_player_started_game(player):
                cube_set_id = self._player_to_cube_set[player]
                await self.hardware.load_rack(self._publish_queue, self.rack_manager.get_rack(player).get_tiles(), cube_set_id, player, now_ms)
            else:
                logging.info(f"LOAD RACK: Skipping player {player} - game not started")

    def _map_position_to_rack(self, position: int) -> tuple[int, int]:
        """
        Map a physical position to a (hit_rack_idx, position_offset) tuple.
        
        Returns:
            hit_rack_idx: The index of the rack (player) that controls this position.
            position_offset: The offset to add to the physical position to get the rack index.
        """
        hit_rack_idx = 0
        position_offset = 0
        
        if self._player_count > 1:
            # 2-Player Logic:
            # Pos 0-2 -> P0 (Rack 0), Offset 0
            # Pos 3-5 -> P1 (Rack 1), Offset -3
            split_idx = game_config.MAX_LETTERS // 2
            hit_rack_idx, position_offset = (0, 0) if position < split_idx else (1, -split_idx)
            
        return hit_rack_idx, position_offset

    async def accept_new_letter(self, next_letter: str, position: int, now_ms: int) -> None:
        # 1. Determine parameters for the manager
        hit_rack_idx, position_offset = self._map_position_to_rack(position)
        
        # 2. Delegate to RackManager
        changed_tile = self.rack_manager.accept_new_letter(
            next_letter, position, hit_rack_idx, position_offset
        )

        self._score_card.update_previous_guesses()
        for player in range(self._player_count):
            cube_set_id = self._player_to_cube_set[player]
            await self.hardware.accept_new_letter(self._publish_queue, next_letter,
                                                  changed_tile.id, cube_set_id, now_ms)

        self._update_previous_guesses()
        self._update_remaining_previous_guesses()
        for player in range(self._player_count):
            events.trigger(RackUpdateLetterEvent(changed_tile, player, now_ms))
        
        self._update_next_tile(self.rack_manager.get_rack(0).next_letter())
        
        if changed_tile.id in self._last_guess:
            for player in range(self._player_count):
                await self.guess_tiles(self._last_guess, False, player, now_ms)

    async def letter_lock(self, position: int, locked: bool, now_ms: int) -> bool:
        hit_rack, position_offset = self._map_position_to_rack(position)

        locked_tile_id = self.rack_manager.get_rack(hit_rack).position_to_id(position + position_offset)

        lock_changed = False
        for player in range(self._player_count):
            cube_set_id = self._player_to_cube_set[player]
            lock_changed |= await self.hardware.letter_lock(self._publish_queue, cube_set_id,
                                            locked_tile_id if locked else None, now_ms)
        return lock_changed

    def add_guess(self, guess: str, player: int) -> None:
        self._score_card.add_guess(guess, player)
        events.trigger(InputAddGuessEvent(self._score_card.get_previous_guesses(), guess, player, self._time.get_ticks()))

    async def remove_highlight(self, word_tile_ids: list[str], player: int) -> None:
        """Remove highlight when cube chain is physically disconnected."""
        logger.info(f"remove_highlight: word_tile_ids {word_tile_ids}")
        self._update_rack_display(0, 0, player, word_tile_ids)
        self._last_guess = []

    async def guess_tiles(self, word_tile_ids: list[str], move_tiles: bool, player: int, now_ms: int) -> None:
        logger.info(f"guess_tiles: word_tile_ids {word_tile_ids}")

        # Empty guess - ignore
        if not word_tile_ids:
            return

        self._last_guess = word_tile_ids

        rack = self.rack_manager.get_rack(player)
        guess = rack.ids_to_letters(word_tile_ids)
        guess_tiles = rack.ids_to_tiles(word_tile_ids)

        print(f"[DEBUG] guess_tiles called:")
        print(f"[DEBUG]   word_tile_ids: {word_tile_ids}")
        print(f"[DEBUG]   player: {player}")
        print(f"[DEBUG]   rack letters: {rack.letters}")
        print(f"[DEBUG]   constructed guess: '{guess}'")
        print(f"[DEBUG]   guess_tiles: {guess_tiles}")

        tiles_dirty = False
        good_guess_highlight = 0
        if move_tiles:
            remaining_tiles = rack.get_tiles().copy()
            for guess_tile in guess_tiles:
                remaining_tiles.remove(guess_tile)
            
            # Update rack content
            if player == 0:
                rack.set_tiles(guess_tiles + remaining_tiles)
            else:
                rack.set_tiles(remaining_tiles + guess_tiles)
            
            tiles_dirty = True

        cube_set_id = self._player_to_cube_set[player]
        print(f"[DEBUG] Checking word validation:")
        print(f"[DEBUG]   is_old_guess('{guess}'): {self._score_card.is_old_guess(guess)}")
        print(f"[DEBUG]   is_good_guess('{guess}'): {self._score_card.is_good_guess(guess)}")

        if self._score_card.is_old_guess(guess):
            print(f"[DEBUG]   Triggering OLD_GUESS event for '{guess}'")
            events.trigger(GameOldGuessEvent(guess, player, self._time.get_ticks()))
            await self.hardware.old_guess(self._publish_queue, word_tile_ids, cube_set_id, player)
            tiles_dirty = True
        elif self._score_card.is_good_guess(guess):
            print(f"[DEBUG]   Triggering STAGE_GUESS event for '{guess}'")
            await self.hardware.good_guess(self._publish_queue, word_tile_ids, cube_set_id, player, now_ms)
            self._score_card.add_staged_guess(guess)
            score = self._score_card.calculate_score(guess)
            events.trigger(GameStageGuessEvent(score, guess, player, now_ms))
            self._word_logger.log_word_formed(guess, player, score, now_ms)
            good_guess_highlight = len(guess_tiles)
            tiles_dirty = True
        else:
            print(f"[DEBUG]   Triggering BAD_GUESS event for '{guess}' (not in dictionary)")
            events.trigger(GameBadGuessEvent(player))
            await self.hardware.bad_guess(self._publish_queue, word_tile_ids, cube_set_id, player)

        # Always update rack display to refresh tile positions from physical cube arrangement
        # For bad guesses, pass highlight_length=0 to avoid creating a highlight
        if tiles_dirty:
            self._update_rack_display(good_guess_highlight, len(guess), player, word_tile_ids)
        else:
            # Bad guess: update tile positions but don't create a highlight
            self._update_rack_display(0, 0, player, None)

    async def guess_word_keyboard(self, guess: str, player: int, now_ms: int) -> None:
        cube_set_id = self._player_to_cube_set[player]
        await self.hardware.guess_tiles(self._publish_queue,
            [self.rack_manager.get_rack(player).letters_to_ids(guess)], cube_set_id, player, now_ms)

    def _update_next_tile(self, next_tile: str) -> None:
        events.trigger(GameNextTileEvent(next_tile, self._time.get_ticks()))

    def _update_previous_guesses(self) -> None:
        events.trigger(InputUpdatePreviousGuessesEvent(
            self._score_card.get_previous_guesses(), self._time.get_ticks()))

    def _update_remaining_previous_guesses(self) -> None:
        events.trigger(InputRemainingPreviousGuessesEvent(
            self._score_card.get_remaining_previous_guesses(),
            self._time.get_ticks()))

    def _update_rack_display(self, highlight_length: int, guess_length: int, player: int, guessed_tile_ids: list[str] | None):
        events.trigger(RackUpdateRackEvent(
                       self.rack_manager.get_rack(player).get_tiles(),
                       highlight_length,
                       guess_length,
                       player,
                       self._time.get_ticks(),
                       guessed_tile_ids))
