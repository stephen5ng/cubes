#!/usr/bin/env python3

import aiomqtt
import pygame
import logging
import time
from typing import Callable, Coroutine, Dict, List

from config import MAX_PLAYERS
import tiles

# Configure logging to print to console
# import sys
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[logging.StreamHandler(sys.stdout)]
# )

# "Cubes" are the MAC address of the ESP32
# "Tiles" are the tile number assigned by the app (usually 0-6)

CUBE_START_MORATORIUM_MS = 2000
_last_game_end_time_ms = 0

# Game state tracking
_game_running = False

# ABC sequence start system
_abc_start_active = False
_abc_cubes = {"A": None, "B": None, "C": None}  # Maps letter to cube ID
class CubeManager:
    def __init__(self, player_number: int):
        self.player_number = player_number
        self.cube_chain: Dict[str, str] = {}
        self.cubes_to_letters: Dict[str, str] = {}
        self.tiles_to_cubes: Dict[str, str] = {}
        self.cubes_to_tileid: Dict[str, str] = {}
        self.cubes_to_neighbors: Dict[str, str] = {}
        self.border_color: str = "0xffff"
        self.cube_list: List[str] = []  # Store ordered list of cubes

    def _find_unmatched_cubes(self):
        sources = set(self.cube_chain.keys())
        targets = set(self.cube_chain.values())
        return list(sources - targets)

    def _print_cube_chain(self):
        if not self.cubes_to_letters:
            return
        try:
            s = f"Player {self.player_number}: "
            for source, target in self.cube_chain.items():
                s += f"{source} [{self.cubes_to_letters.get(source, '')}] -> {target} [{self.cubes_to_letters.get(target, '')}]; "
            return s
        except Exception as e:
            logging.error(f"print_cube_chain ERROR: {e}")

    def _dump_cubes_to_neighbors(self):
        # Prefer explicit cube list for stable ordering
        cubes_iter = list(self.cube_list)
        for cube in cubes_iter:
            log_str = f"Player {self.player_number}: {cube} [{self.cubes_to_letters.get(cube, '')}]"
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
        start_idx = self.player_number * tiles.MAX_LETTERS
        end_idx = start_idx + tiles.MAX_LETTERS
        
        cubes = all_cubes[start_idx:end_idx]
        self.cube_list = cubes
        self._initialize_arrays()

    async def load_rack(self, publish_queue, tiles_with_letters: list[tiles.Tile], now_ms: int) -> None:
        """Load letters onto the rack for this player."""
        logging.info(f"LOAD RACK tiles_with_letters: {tiles_with_letters}")
        for tile in tiles_with_letters:
            tile_id = tile.id
            cube_id = self.tiles_to_cubes[tile_id]
            letter = tile.letter
            self.cubes_to_letters[cube_id] = letter
            await _publish_letter(publish_queue, letter, cube_id, now_ms)
            if letter == " ":
                # Clear all borders for empty cubes using consolidated messaging
                await publish_queue.put((f"cube/{cube_id}/border", ":", True, now_ms))
        logging.info(f"LOAD RACK tiles_with_letters done: {self.cubes_to_letters}")

    async def _mark_tiles_for_guess(self, publish_queue, guess_tiles: List[str], now_ms: int) -> None:
        """Mark tiles as used/unused for a guess."""
        # Only draw borders when game is running
        if not _game_running:
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
        for t in tiles:
            await publish_queue.put((f"cube/{self.tiles_to_cubes[t]}/flash", "1", False, now_ms))

class GuessManager:
    def __init__(self):
        self.last_tiles_with_letters: list[tiles.Tile] = []
        self.last_guess_tiles: List[str] = []
        self.last_guess_time_s = time.time()
        self.DEBOUNCE_TIME_S = 10

    async def guess_tiles(self, publish_queue, word_tiles_list, player: int, now_ms: int):
        self.last_guess_tiles = word_tiles_list
        await guess_last_tiles(publish_queue, player, now_ms)

    async def load_rack(self, publish_queue, tiles_with_letters: list[tiles.Tile], player: int, now_ms: int):
        await cube_managers[player].load_rack(publish_queue, tiles_with_letters, now_ms)

        if self.last_tiles_with_letters != tiles_with_letters:
            # Some of the tiles changed. Make a guess, just in case one of them
            # was in our last guess (which is overkill).
            logging.info(f"LOAD RACK guessing")
            await guess_last_tiles(publish_queue, player, now_ms)
            self.last_tiles_with_letters = tiles_with_letters

# Global managers for each player
cube_managers: List[CubeManager] = [CubeManager(player) for player in range(MAX_PLAYERS)]
# Global mapping of cube IDs to player numbers for O(1) lookup
cube_to_player: Dict[str, int] = {}
# Global guess manager
guess_manager = GuessManager()

async def _publish_letter(publish_queue, letter, cube_id, now_ms):
    await publish_queue.put((f"cube/{cube_id}/letter", letter, True, now_ms))

async def accept_new_letter(publish_queue, letter, tile_id, player: int, now_ms: int):
    cube_id = cube_managers[player].tiles_to_cubes[tile_id]
    cube_managers[player].cubes_to_letters[cube_id] = letter
    await _publish_letter(publish_queue, letter, cube_id, now_ms)

async def load_rack(publish_queue, tiles_with_letters: list[tiles.Tile], player: int, now_ms: int):
    await guess_manager.load_rack(publish_queue, tiles_with_letters, player, now_ms)

async def guess_tiles(publish_queue, word_tiles_list, player: int, now_ms: int):
    await guess_manager.guess_tiles(publish_queue, word_tiles_list, player, now_ms)

guess_tiles_callback: Callable[[str, bool], Coroutine[None, None, None]]

def set_guess_tiles_callback(f):
    global guess_tiles_callback
    guess_tiles_callback = f

def set_start_game_callback(f):
    global start_game_callback
    start_game_callback = f

locked_cubes = {}
async def letter_lock(publish_queue, player, tile_id: str | None, now_ms: int) -> bool:
    global locked_cubes
    cube_id = cube_managers[player].tiles_to_cubes.get(tile_id) if tile_id else None

    if last_cube_id := locked_cubes.get(player, None):    
        if last_cube_id == cube_id:
            return False

        # Unlock last cube
        await publish_queue.put((f"cube/{last_cube_id}/lock", None, True, now_ms))
        
    locked_cubes[player] = cube_id
    if cube_id:
        await publish_queue.put((f"cube/{cube_id}/lock", "1", True, now_ms))
    return True

async def guess_last_tiles(publish_queue, player: int, now_ms: int) -> None:
    logging.info(f"guess_last_tiles last_guess_tiles {guess_manager.last_guess_tiles}")
    for guess in guess_manager.last_guess_tiles:
        await guess_tiles_callback(guess, True, player, now_ms)

    await cube_managers[player]._mark_tiles_for_guess(publish_queue, guess_manager.last_guess_tiles, now_ms)

async def flash_guess(publish_queue, tiles: list[str], player: int, now_ms: int):
    await cube_managers[player].flash_guess(publish_queue, tiles, now_ms)

def set_game_end_time(now_ms: int) -> None:
    """Track when the game ended to enforce moratorium period."""
    global _last_game_end_time_ms, _game_running
    _last_game_end_time_ms = now_ms
    _game_running = False
    logging.info(f"Game ended at {now_ms}, cube start moratorium active for {CUBE_START_MORATORIUM_MS}ms")

async def clear_all_borders(publish_queue, now_ms: int) -> None:
    """Clear all borders on all cubes across all players using consolidated messaging."""
    for manager in cube_managers:
        for cube_id in manager.cube_list:
            # Use consolidated border protocol: ":" clears all borders
            await publish_queue.put((f"cube/{cube_id}/border", ":", True, now_ms))

async def clear_all_letters(publish_queue, now_ms: int) -> None:
    """Clear letters on all cubes across all players by setting space and retaining."""
    for manager in cube_managers:
        for cube_id in manager.cube_list:
            await publish_queue.put((f"cube/{cube_id}/letter", " ", True, now_ms))

def set_game_running(running: bool) -> None:
    """Set the current game running state."""
    global _game_running
    _game_running = running
    logging.info(f"Game running state set to: {running}")
    
    # Clear ABC sequence when game starts
    if running:
        _clear_abc_start_sequence()

async def _find_non_touching_cubes(publish_queue, now_ms: int) -> List[str]:
    """Find 3 cubes that are not touching each other."""
    # Get all available cubes from the first cube manager
    if not cube_managers or not cube_managers[0].cube_list:
        return []
    
    all_cubes = list(cube_managers[0].cube_list)
    
    if len(all_cubes) < 3:
        return []
    
    # With 6 cubes total and no cycles possible, we can always find 3 non-touching cubes
    # Simple approach: iterate through cubes and pick ones that aren't connected
    selected_cubes = []
    
    for cube in all_cubes:
        if len(selected_cubes) >= 3:
            break
            
        # Check if this cube is touching any already selected cube
        is_touching_selected = False
        for selected_cube in selected_cubes:
            # Check if cube -> selected_cube or selected_cube -> cube connection exists
            for manager in cube_managers:
                if (manager.cube_chain.get(cube) == selected_cube or
                    manager.cube_chain.get(selected_cube) == cube):
                    is_touching_selected = True
                    break
            if is_touching_selected:
                break
        
        if not is_touching_selected:
            selected_cubes.append(cube)
    
    return selected_cubes[:3]

async def _activate_abc_start_sequence(publish_queue, now_ms: int) -> None:
    """Activate the ABC sequence start system after moratorium."""
    global _abc_start_active, _abc_cubes
    
    # Find 3 non-touching cubes
    selected_cubes = await _find_non_touching_cubes(publish_queue, now_ms)
    if len(selected_cubes) < 3:
        logging.warning("Not enough cubes available for ABC start sequence")
        return
    
    # Assign A, B, C to the selected cubes
    letters = ["A", "B", "C"]
    for i, letter in enumerate(letters):
        _abc_cubes[letter] = selected_cubes[i]
    
    _abc_start_active = True
    logging.info(f"ABC start sequence activated: {_abc_cubes}")
    print(f"ABC start sequence activated: {_abc_cubes}")
    
    # Display A, B, C on the selected cubes
    for letter, cube_id in _abc_cubes.items():
        logging.info(f"ABC: publishing letter {letter} to cube {cube_id}")
        await _publish_letter(publish_queue, letter, cube_id, now_ms)

async def _check_abc_sequence_complete() -> bool:
    """Check if A-B-C cubes are placed in sequence."""
    if not _abc_start_active or not all(_abc_cubes.values()):
        return False
    
    # Check all cube managers for the ABC sequence
    for manager in cube_managers:
        # Look for A-B-C in the cube chain
        logging.info(f"ABC check: manager {manager.player_number} cube_chain={manager.cube_chain}")
        cube_a = _abc_cubes["A"]
        cube_b = _abc_cubes["B"] 
        cube_c = _abc_cubes["C"]
        
        # Check if A->B->C chain exists
        if (cube_a in manager.cube_chain and 
            manager.cube_chain[cube_a] == cube_b and
            cube_b in manager.cube_chain and 
            manager.cube_chain[cube_b] == cube_c):
            return True
    
    return False

def _clear_abc_start_sequence() -> None:
    """Clear the ABC start sequence state."""
    global _abc_start_active, _abc_cubes
    _abc_start_active = False
    _abc_cubes = {"A": None, "B": None, "C": None}
    logging.info("ABC start sequence cleared")

def _all_cubes_have_reported_neighbors() -> bool:
    """Check if all cubes have reported their neighbor status (including '-')."""
    if not cube_managers:
        return False    
    
    for manager in cube_managers:
        all_cubes = set(manager.cube_list)
        reported_cubes = set(manager.cubes_to_neighbors.keys())
        # print(f"all_cubes: {all_cubes}, reported_cubes: {reported_cubes}")
        if all_cubes.issubset(reported_cubes):
            # print(f"all cubes have neighbors")
            return True
        else:
            missing_cubes = all_cubes - reported_cubes
            if missing_cubes:  # Only print if there are actually missing cubes
                print(f"Player {manager.player_number}: Still waiting for neighbor reports from cubes: {missing_cubes}")
    
    return False

async def activate_abc_start_if_ready(publish_queue, now_ms: int) -> None:
    """Activate ABC start sequence if conditions are met (public interface)."""
    if (not _abc_start_active and not _game_running and 
        (_last_game_end_time_ms == 0 or _is_cube_start_allowed(now_ms))):
        await _activate_abc_start_sequence(publish_queue, now_ms)

def _is_cube_start_allowed(now_ms: int) -> bool:
    """Check if cube-based game start is allowed (outside moratorium period)."""
    global _last_game_end_time_ms
    if _last_game_end_time_ms == 0:
        return True  # No previous game end recorded
    
    time_since_end = now_ms - _last_game_end_time_ms
    return time_since_end >= CUBE_START_MORATORIUM_MS

    

async def init(subscribe_client):
    # Subscribe to direct neighbor topics only
    await subscribe_client.subscribe("cube/right/#")
    
    all_cubes = [str(i) for i in range(1, 14)]

    # Clear and rebuild the global cube_to_player mapping
    cube_to_player.clear()
    
    # Initialize managers for each player
    for player, manager in enumerate(cube_managers):
        await manager.init(all_cubes)
        # Add to global cube_to_player mapping
        for cube in manager.cube_list:
            cube_to_player[cube] = player
    logging.info(f"INIT: cube_list p0={cube_managers[0].cube_list} p1={cube_managers[1].cube_list}")
    logging.info(f"INIT: cube_to_player={cube_to_player}")

async def handle_mqtt_message(publish_queue, message, now_ms: int):
    topic_str = getattr(message.topic, 'value', str(message.topic))
    payload_data = message.payload.decode() if message.payload is not None else ""
    logging.info(f"MQTT recv: topic={topic_str} payload={payload_data}")
    
    # Direct neighbor cube id from /cube/right/SENDER
    if topic_str.startswith("cube/right/"):
        sender_cube = topic_str.removeprefix("cube/right/")
        neighbor_cube = payload_data
        player = cube_to_player.get(sender_cube)
        if player is not None:
            logging.info(f"RIGHT msg: sender={sender_cube} neighbor={neighbor_cube} player={player}")
            word_tiles_list = cube_managers[player].process_neighbor_cube(sender_cube, neighbor_cube)
            logging.info(f"WORD_TILES (right): {word_tiles_list}")
            await guess_tiles(publish_queue, word_tiles_list, player, now_ms)

            # Check ABC completion after processing right-edge updates
            if _abc_start_active and await _check_abc_sequence_complete():
                logging.info("ABC sequence complete! Starting game (right)")
                print("ABC sequence complete! Starting game (right)")
                _clear_abc_start_sequence()
                await start_game_callback(True, now_ms)
        return


async def good_guess(publish_queue, tiles: list[str], player: int, now_ms: int):
    cube_managers[player].border_color = "0x07E0"
    await flash_guess(publish_queue, tiles, player, now_ms)

async def old_guess(publish_queue, tiles: list[str], player: int):
    cube_managers[player].border_color = "0xFFE0"

async def bad_guess(publish_queue, tiles: list[str], player: int):
    cube_managers[player].border_color = "0xFFFF"
