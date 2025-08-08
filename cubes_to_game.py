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

# "Tags" are nfc ids
# "Cubes" are the MAC address of the ESP32
# "Tiles" are the tile number assigned by the app (usually 0-6)

START_GAME_TAGS = ["E8F21366080104E0"]

# Moratorium period configuration
CUBE_START_MORATORIUM_MS = 15000  # 15 seconds by default, configurable
_last_game_end_time_ms = 0

# Game state tracking
_game_running = False

# ABC sequence start system
_abc_start_active = False
_abc_cubes = {"A": None, "B": None, "C": None}  # Maps letter to cube ID
class CubeManager:
    def __init__(self, player_number: int):
        self.player_number = player_number
        self.tags_to_cubes: Dict[str, str] = {}
        self.cube_chain: Dict[str, str] = {}
        self.cubes_to_letters: Dict[str, str] = {}
        self.tiles_to_cubes: Dict[str, str] = {}
        self.cubes_to_tileid: Dict[str, str] = {}
        self.cubes_to_neighbortags: Dict[str, str] = {}
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

    def _dump_cubes_to_neighbortags(self):
        for cube in self.tags_to_cubes.values():
            log_str = f"Player {self.player_number}: {cube} [{self.cubes_to_letters.get(cube, '')}]"
            if cube in self.cubes_to_neighbortags:
                neighbor = self.cubes_to_neighbortags[cube]
                neighbor_cube = self.tags_to_cubes.get(neighbor, "")
                log_str += f"-> {neighbor},{neighbor_cube}"
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

    def process_tag(self, sender_cube: str, tag: str) -> List[str]:
        # Update neighbor tracking
        self.cubes_to_neighbortags[sender_cube] = tag
        self._dump_cubes_to_neighbortags()
        logging.info(f"process_tag {sender_cube}: {tag}")
        logging.info(f"process_tag cube_chain {self.cube_chain}")

        # Handle empty or invalid tag case
        if not tag or tag not in self.tags_to_cubes:
            logging.info(f"bad tag: {tag}")
            if sender_cube in self.cube_chain:
                del self.cube_chain[sender_cube]
            return self._form_words_from_chain()

        target_cube = self.tags_to_cubes[tag]
        
        # Update chain if valid
        if not self._update_chain(sender_cube, target_cube):
            return []

        logging.info(f"process_tag final cube_chain: {self._print_cube_chain()}")
        return self._form_words_from_chain()

    def _initialize_arrays(self):
        cubes = list(self.tags_to_cubes.values())
        self.tiles_to_cubes = {str(i): cubes[i] for i in range(len(cubes))}
        self.cubes_to_tileid = {cube: tile_id for tile_id, cube in self.tiles_to_cubes.items()}

    async def init(self, all_cubes: List[str], all_tags: List[str]):
        """Initialize cube manager for a specific player."""
        start_idx = self.player_number * tiles.MAX_LETTERS
        end_idx = start_idx + tiles.MAX_LETTERS
        
        cubes = all_cubes[start_idx:end_idx]
        tags = all_tags[start_idx:end_idx]

        self.tags_to_cubes = {tag: cube for cube, tag in zip(cubes, tags)}
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
                await publish_queue.put((f"cube/{cube_id}/border_hline_top", None, True, now_ms))
                await publish_queue.put((f"cube/{cube_id}/border_hline_bottom", None, True, now_ms))
                await publish_queue.put((f"cube/{cube_id}/border_vline_left", None, True, now_ms))
                await publish_queue.put((f"cube/{cube_id}/border_vline_right", None, True, now_ms))
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
                await publish_queue.put(
                    (f"cube/{self.tiles_to_cubes[tile]}/border_hline_top", self.border_color, True, now_ms))
                await publish_queue.put(
                    (f"cube/{self.tiles_to_cubes[tile]}/border_hline_bottom", self.border_color, True, now_ms))
                await publish_queue.put(
                    (f"cube/{self.tiles_to_cubes[tile]}/border_vline_left",
                                         self.border_color if i == 0 else "",
                                         not(i == 0), now_ms))
                await publish_queue.put(
                    (f"cube/{self.tiles_to_cubes[tile]}/border_vline_right",
                                         self.border_color if i == len(guess)-1 else "",
                                         not(i == len(guess)-1), now_ms))

        for tile in unused_tiles:
            await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_hline_top", None, True, now_ms))
            await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_hline_bottom", None, True, now_ms))
            await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_vline_left", None, True, now_ms))
            await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_vline_right", None, True, now_ms))

    async def flash_guess(self, publish_queue, tiles: list[str], now_ms: int) -> None:
        for t in tiles:
            await publish_queue.put((f"cube/{self.tiles_to_cubes[t]}/flash", "1", False, now_ms))

class GuessManager:
    def __init__(self):
        self.last_tiles_with_letters: list[tiles.Tile] = []
        self.last_guess_tiles: List[str] = []
        self.last_guess_time_s = time.time()
        self.DEBOUNCE_TIME_S = 10

    async def guess_word_based_on_cubes(self, sender: str, tag: str, publish_queue, cube_to_player: Dict[str, int], cube_managers: List[CubeManager], now_ms: int):
        now_s = now_ms / 1000
        
        player = cube_to_player.get(sender)
        if player is None:
            logging.error(f"Unknown cube: {sender}")
            return
        
        word_tiles_list = cube_managers[player].process_tag(sender, tag)
        logging.info(f"WORD_TILES: {word_tiles_list}")
        if word_tiles_list == self.last_guess_tiles and now_s - self.last_guess_time_s < self.DEBOUNCE_TIME_S:
            logging.info(f"debounce ignoring guess")
            self.last_guess_time_s = now_s
            return
        self.last_guess_time_s = now_s
        await self.guess_tiles(publish_queue, word_tiles_list, player, now_ms)

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

async def guess_word_based_on_cubes(sender: str, tag: str, publish_queue, now_ms: int):
    await guess_manager.guess_word_based_on_cubes(sender, tag, publish_queue, cube_to_player, cube_managers, now_ms)

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
    if not cube_managers or not cube_managers[0].tags_to_cubes:
        return []
    
    all_cubes = list(cube_managers[0].tags_to_cubes.values())
    
    if len(all_cubes) < 3:
        return []
    
    # Find 3 cubes that are not connected to each other
    # We need to ensure none of the selected cubes are directly connected
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
    
    # If we couldn't find 3 non-touching cubes, just use any 3 cubes
    # This ensures the system always works even if all cubes are connected
    if len(selected_cubes) >= 3:
        return selected_cubes[:3]
    else:
        return all_cubes[:3]

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
    
    # Display A, B, C on the selected cubes
    for letter, cube_id in _abc_cubes.items():
        await _publish_letter(publish_queue, letter, cube_id, now_ms)

async def _check_abc_sequence_complete() -> bool:
    """Check if A-B-C cubes are placed in sequence."""
    if not _abc_start_active or not all(_abc_cubes.values()):
        return False
    
    # Check all cube managers for the ABC sequence
    for manager in cube_managers:
        # Look for A-B-C in the cube chain
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

async def process_cube_guess(publish_queue, topic: aiomqtt.Topic, data: str, now_ms: int):
    global _abc_start_active
    logging.info(f"process_cube_guess: {topic} {data}")
    sender = topic.value.removeprefix("cube/nfc/")
    await publish_queue.put((f"game/nfc/{sender}", data, True, now_ms))
    
    # Handle special START_GAME_TAGS (legacy method)
    if data in START_GAME_TAGS:
        if _is_cube_start_allowed(now_ms):
            await start_game_callback(True, now_ms)
        else:
            time_remaining = CUBE_START_MORATORIUM_MS - (now_ms - _last_game_end_time_ms)
            logging.info(f"Cube start blocked by moratorium, {time_remaining}ms remaining")
        return
    
    # Check if moratorium just expired and we should activate ABC sequence
    if (not _abc_start_active and not _game_running and 
        _last_game_end_time_ms > 0 and _is_cube_start_allowed(now_ms)):
        await _activate_abc_start_sequence(publish_queue, now_ms)
    
    # Process normal cube interactions
    await guess_word_based_on_cubes(sender, data, publish_queue, now_ms)
    
    # Check if ABC sequence is complete and start game
    if _abc_start_active and await _check_abc_sequence_complete():
        logging.info("ABC sequence complete! Starting game...")
        _clear_abc_start_sequence()
        await start_game_callback(True, now_ms)

def read_data(f) -> List[str]:
    """Read all data from file."""
    data = f.readlines()
    return [l.strip() for l in data]

async def init(subscribe_client, tags_file):
    await subscribe_client.subscribe("cube/nfc/#")
    
    all_cubes = [str(i) for i in range(1, 14)]

    # Read all data first
    with open(tags_file) as tags_f:
        all_tags = read_data(tags_f)
    
    # Clear and rebuild the global cube_to_player mapping
    cube_to_player.clear()
    
    # Initialize managers for each player
    for player, manager in enumerate(cube_managers):
        await manager.init(all_cubes, all_tags)
        
        # Add to global cube_to_player mapping
        for cube in manager.cube_list:
            cube_to_player[cube] = player

async def handle_mqtt_message(publish_queue, message, now_ms: int):
    payload_data = message.payload.decode() if message.payload is not None else ""
    await process_cube_guess(publish_queue, message.topic, payload_data, now_ms)

async def good_guess(publish_queue, tiles: list[str], player: int, now_ms: int):
    cube_managers[player].border_color = "0x07E0"
    await flash_guess(publish_queue, tiles, player, now_ms)

async def old_guess(publish_queue, tiles: list[str], player: int):
    cube_managers[player].border_color = "0xFFE0"

async def bad_guess(publish_queue, tiles: list[str], player: int):
    cube_managers[player].border_color = "0xFFFF"
