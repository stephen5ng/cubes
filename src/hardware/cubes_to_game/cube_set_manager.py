"""Cube set and guess management for BlockWords hardware.

This module contains CubeSetManager for managing a single player's cube state,
and GuessManager for debouncing and coordinating guess submissions.
"""

import logging
import time
from typing import Dict, List

from core import tiles


class CubeSetManager:
    """Manages state for a single player's cube set (typically 6 cubes)."""

    def __init__(self, cube_set_id: int):
        self.cube_set_id = cube_set_id
        self.cube_chain: Dict[str, str] = {}
        self.cubes_to_letters: Dict[str, str] = {}
        self.tiles_to_cubes: Dict[str, str] = {}
        self.cubes_to_tileid: Dict[str, str] = {}
        self.cubes_to_neighbors: Dict[str, str] = {}
        self.border_color: str = "0xFFFF"
        self.cube_list: List[str] = []  # Store ordered list of cubes

    def _find_unmatched_cubes(self):
        sources = set(self.cube_chain.keys())
        targets = set(self.cube_chain.values())
        return list(sources - targets)

    def _print_cube_chain(self):
        if not self.cubes_to_letters:
            return
        try:
            s = f"Cube set {self.cube_set_id}: "
            for source, target in self.cube_chain.items():
                s += f"{source} [{self.cubes_to_letters.get(source, '')}] -> {target} [{self.cubes_to_letters.get(target, '')}]; "
            return s
        except Exception as e:
            logging.error(f"print_cube_chain ERROR: {e}")

    def _dump_cubes_to_neighbors(self):
        # Prefer explicit cube list for stable ordering
        cubes_iter = list(self.cube_list)
        for cube in cubes_iter:
            log_str = f"Cube set {self.cube_set_id}: {cube} [{self.cubes_to_letters.get(cube, '')}]"
            if cube in self.cubes_to_neighbors:
                neighbor_cube = self.cubes_to_neighbors[cube]
                log_str += f"-> {neighbor_cube}"
                log_str += f"[{self.cubes_to_letters.get(neighbor_cube, '')}]"
            logging.info(log_str)
        logging.info("")

    def _form_words_from_chain(self) -> List[str]:
        """Forms words from the current cube chain. Returns empty list if invalid."""
        if not self.cube_chain:
            return []

        source_cubes = self._find_unmatched_cubes()
        all_words = []
        for source_cube in sorted(source_cubes):
            word_tiles = []
            sc = source_cube
            while sc:
                if sc not in self.cubes_to_tileid:
                    return []
                word_tiles.append(self.cubes_to_tileid[sc])
                if len(word_tiles) > tiles.MAX_LETTERS:
                    logging.info("infinite loop")
                    return []
                sc = self.cube_chain.get(sc)
            all_words.append("".join(word_tiles))

        # Check for duplicates
        all_elements = [item for lst in all_words for item in lst]
        if len(all_elements) != len(set(all_elements)):
            logging.info(f"DUPES: {all_words}")
            return []

        return all_words

    def _has_loop_from_cube(self, start_cube: str) -> bool:
        """Checks if adding a link from start_cube would create a loop."""
        path = {start_cube}
        curr = self.cube_chain.get(start_cube)
        while curr:
            if curr in path:
                return True
            path.add(curr)
            curr = self.cube_chain.get(curr)
        return False

    def _update_chain(self, sender_cube: str, target_cube: str) -> bool:
        """Updates the chain with a new connection. Returns True if chain is valid."""
        if sender_cube == target_cube:
            return False

        self.cube_chain[sender_cube] = target_cube
        if self._has_loop_from_cube(sender_cube):
            del self.cube_chain[sender_cube]
            return False
        return True

    def process_neighbor_cube(self, sender_cube: str, neighbor_cube: str) -> List[str]:
        # Update neighbor tracking with direct cube id
        self.cubes_to_neighbors[sender_cube] = neighbor_cube
        self._dump_cubes_to_neighbors()
        logging.info(f"process_neighbor_cube {sender_cube} -> {neighbor_cube}")

        # Handle empty or invalid neighbor case
        if not neighbor_cube or neighbor_cube not in self.cube_list:
            if sender_cube in self.cube_chain:
                del self.cube_chain[sender_cube]
            return self._form_words_from_chain()

        # Update chain if valid
        if not self._update_chain(sender_cube, neighbor_cube):
            return []
        logging.info(f"process_neighbor final cube_chain: {self._print_cube_chain()}")
        return self._form_words_from_chain()

    def _initialize_arrays(self):
        cubes = self.cube_list
        self.tiles_to_cubes = {str(i): cubes[i] for i in range(len(cubes))}
        self.cubes_to_tileid = {cube: tile_id for tile_id, cube in self.tiles_to_cubes.items()}

    async def init(self, all_cubes: List[str]):
        """Initialize cube manager for a specific player."""
        start_idx = self.cube_set_id * tiles.MAX_LETTERS
        end_idx = start_idx + tiles.MAX_LETTERS

        cubes = all_cubes[start_idx:end_idx]
        self.cube_list = cubes
        self._initialize_arrays()

    async def load_rack(self, publish_queue, tiles_with_letters: list[tiles.Tile], now_ms: int, game_started_players: set) -> None:
        """Load letters onto the rack for this player.

        Args:
            publish_queue: Queue for MQTT messages
            tiles_with_letters: List of tiles to load
            now_ms: Current timestamp
            game_started_players: Set of players who have started
        """
        # Only load letters if this player has started their game
        if self.cube_set_id not in game_started_players:
            logging.info(f"LOAD RACK: Cube set {self.cube_set_id} game not started, skipping letter loading")
            return

        logging.info(f"LOAD RACK tiles_with_letters: {tiles_with_letters}")
        for tile in tiles_with_letters:
            tile_id = tile.id
            cube_id = self.tiles_to_cubes[tile_id]
            letter = tile.letter
            self.cubes_to_letters[cube_id] = letter
            # Publish letter - will be handled by coordination layer
            await publish_queue.put((f"cube/{cube_id}/letter", letter, True, now_ms))
            if letter == " ":
                # Clear all borders for empty cubes using consolidated messaging
                await publish_queue.put((f"cube/{cube_id}/border", ":", True, now_ms))
        logging.info(f"LOAD RACK tiles_with_letters done: {self.cubes_to_letters}")

    async def _mark_tiles_for_guess(self, publish_queue, guess_tiles: List[str], now_ms: int, game_started_players: set) -> None:
        """Mark tiles as used/unused for a guess.

        Args:
            publish_queue: Queue for MQTT messages
            guess_tiles: List of tile IDs in the guess
            now_ms: Current timestamp
            game_started_players: Set of players who have started
        """
        # Only draw borders when this player's game is running
        if self.cube_set_id not in game_started_players:
            return

        unused_tiles = sorted(list(set((str(i) for i in range(tiles.MAX_LETTERS)))))
        for guess in guess_tiles:
            for i, tile in enumerate(guess):
                unused_tiles.remove(tile)

                # Build consolidated border message for this tile
                directions = ["N", "S"]  # Always include top and bottom

                if i == 0:  # First letter in word
                    directions.append("W")  # Add left border
                if i == len(guess) - 1:  # Last letter in word
                    directions.append("E")  # Add right border

                # Create consolidated message: "NS:color", "NSW:color", "NSE:color", or "NSEW:color"
                consolidated_message = f"{''.join(sorted(directions))}:{self.border_color}"
                await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border", consolidated_message, True, now_ms))

        for tile in unused_tiles:
            # Clear all borders for unused tiles using consolidated messaging
            await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border", ":", True, now_ms))

    async def flash_guess(self, publish_queue, tiles: list[str], now_ms: int) -> None:
        """Flash the tiles for a guess."""
        for t in tiles:
            await publish_queue.put((f"cube/{self.tiles_to_cubes[t]}/flash", "1", False, now_ms))


class GuessManager:
    """Manages guess debouncing and coordination."""

    def __init__(self):
        self.last_tiles_with_letters: list[tiles.Tile] = []
        self.last_guess_tiles: List[str] = []
        self.last_guess_time_s = time.time()
        self.DEBOUNCE_TIME_S = 10

    async def guess_tiles(self, publish_queue, word_tiles_list, cube_set_id: int, player: int, now_ms: int,
                          guess_last_tiles_func) -> None:
        """Submit a guess for tiles.

        Args:
            publish_queue: Queue for MQTT messages
            word_tiles_list: List of tile IDs to guess
            cube_set_id: Which player's cube set
            player: Player number
            now_ms: Current timestamp
            guess_last_tiles_func: Function to call to process the guess
        """
        self.last_guess_tiles = word_tiles_list
        await guess_last_tiles_func(publish_queue, cube_set_id, player, now_ms)

    async def load_rack(self, publish_queue, tiles_with_letters: list[tiles.Tile], cube_set_id: int, player: int,
                        now_ms: int, cube_set_manager, game_started_players: set, guess_last_tiles_func) -> None:
        """Load rack and potentially submit a guess if tiles changed.

        Args:
            publish_queue: Queue for MQTT messages
            tiles_with_letters: Tiles to load
            cube_set_id: Which player's cube set
            player: Player number
            now_ms: Current timestamp
            cube_set_manager: The CubeSetManager instance to use
            game_started_players: Set of players who have started
            guess_last_tiles_func: Function to call to process guesses
        """
        await cube_set_manager.load_rack(publish_queue, tiles_with_letters, now_ms, game_started_players)

        if self.last_tiles_with_letters != tiles_with_letters:
            # Some of the tiles changed. Make a guess, just in case one of them
            # was in our last guess (which is overkill).
            logging.info(f"LOAD RACK guessing")
            await guess_last_tiles_func(publish_queue, cube_set_id, player, now_ms)
            self.last_tiles_with_letters = tiles_with_letters
