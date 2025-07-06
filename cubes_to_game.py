#!/usr/bin/env python3

import aiomqtt
import logging
import time
from typing import Callable, Coroutine, Dict, List

from config import PLAYER_COUNT
import tiles

# Configure logging to print to console
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[logging.StreamHandler(sys.stdout)]
# )

# "Tags" are nfc ids
# "Cubes" are the MAC address of the ESP32
# "Tiles" are the tile number assigned by the app (usually 0-6)

START_GAME_CUBES = ["E8F21366080104E0"]
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
            for source in self.cube_chain:
                target = self.cube_chain[source]
                s += f"{source} [{self.cubes_to_letters[source]}] -> {target} [{self.cubes_to_letters[target]}]; "
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

        all_words = []
        source_cubes = self._find_unmatched_cubes()
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
                if sc not in self.cube_chain:
                    break
                sc = self.cube_chain[sc]
            all_words.append("".join(word_tiles))

        # Check for duplicates
        all_elements = [item for lst in all_words for item in lst]
        if len(all_elements) != len(set(all_elements)):
            logging.info(f"DUPES: {all_words}")
            return []

        return all_words

    def _has_loop_from_cube(self, start_cube: str) -> bool:
        """Checks if adding a link from start_cube would create a loop.
        Returns True if a loop is detected, False otherwise."""
        source_cube = start_cube
        iter_length = 0
        while source_cube:
            iter_length += 1
            if iter_length > tiles.MAX_LETTERS:
                logging.info(f"forever loop, bailing")
                return True
            if not source_cube in self.cube_chain:
                break
            next_cube = self.cube_chain[source_cube]
            if next_cube == start_cube:
                logging.info(f"breaking chain {self._print_cube_chain()}")
                return True
            source_cube = next_cube
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

        # Handle empty tag case
        if not tag:
            logging.info(f"process_tag: no tag, deleting target of {sender_cube}")
            if sender_cube in self.cube_chain:
                del self.cube_chain[sender_cube]
            return self._form_words_from_chain()

        # Validate tag and cube
        if tag not in self.tags_to_cubes:
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
        self.tiles_to_cubes.clear()
        self.cubes_to_tileid.clear()

        cubes = list(self.tags_to_cubes.values())
        for ix in range(tiles.MAX_LETTERS+1):
            if ix >= len(cubes):
                break
            tile_id = str(ix)
            self.tiles_to_cubes[tile_id] = cubes[ix]
            self.cubes_to_tileid[cubes[ix]] = tile_id

    def get_tags_to_cubes(self, cubes_file: str, tags_file: str):
        with open(cubes_file) as cubes_f:
            with open(tags_file) as tags_f:
                return self.get_tags_to_cubes_f(cubes_f, tags_f)

    def get_tags_to_cubes_f(self, cubes_f, tags_f):
        cubes = read_data(cubes_f)
        tags = read_data(tags_f)
        self.cube_list = cubes  # Store ordered list of cubes
        return {tag: cube for cube, tag in zip(cubes, tags)}

    async def init(self, subscribe_client, cubes_file, tags_file):
        logging.info("cubes_to_game")
        self.tags_to_cubes = self.get_tags_to_cubes(cubes_file, tags_file)
        logging.info(f"ttc: {self.tags_to_cubes}")

        self._initialize_arrays()

    async def load_rack(self, publish_queue, tiles_with_letters: list[tiles.Tile]) -> None:
        """Load letters onto the rack for this player."""
        logging.info(f"LOAD RACK tiles_with_letters: {tiles_with_letters}")
        for tile in tiles_with_letters:
            tile_id = tile.id
            cube_id = self.tiles_to_cubes[tile_id]
            letter = tile.letter
            self.cubes_to_letters[cube_id] = letter
            await _publish_letter(publish_queue, letter, cube_id)
            if letter == " ":
                await publish_queue.put((f"cube/{cube_id}/border_hline_top", "", False))
                await publish_queue.put((f"cube/{cube_id}/border_hline_bottom", "", False))
                await publish_queue.put((f"cube/{cube_id}/border_vline_left", "", False))
                await publish_queue.put((f"cube/{cube_id}/border_vline_right", "", False))
        logging.info(f"LOAD RACK tiles_with_letters done: {self.cubes_to_letters}")

    async def _mark_tiles_for_guess(self, publish_queue, guess_tiles: List[str]) -> None:
        """Mark tiles as used/unused for a guess."""
        unused_tiles = set((str(i) for i in range(tiles.MAX_LETTERS)))
        for guess in guess_tiles:
            for i, tile in enumerate(guess):
                unused_tiles.remove(tile)
                await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_hline_top", self.border_color, True))
                await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_hline_bottom", self.border_color, True))
                await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_vline_left",
                                         self.border_color if i == 0 else "", not(i == 0)))
                await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_vline_right",
                                         self.border_color if i == len(guess)-1 else "", not(i == len(guess)-1)))

        for tile in unused_tiles:
            await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_hline_top", "", False))
            await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_hline_bottom", "", False))
            await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_vline_left", "", False))
            await publish_queue.put((f"cube/{self.tiles_to_cubes[tile]}/border_vline_right", "", False))

    async def flash_guess(self, publish_queue, tiles: list[str]) -> None:
        for t in tiles:
            await publish_queue.put((f"cube/{self.tiles_to_cubes[t]}/flash", None, False))

class GuessManager:
    def __init__(self):
        self.last_tiles_with_letters: list[tiles.Tile] = []
        self.last_guess_tiles: List[str] = []
        self.last_guess_time_s = time.time()
        self.DEBOUNCE_TIME_S = 10

    async def guess_word_based_on_cubes(self, sender: str, tag: str, publish_queue, cube_to_player: Dict[str, int], cube_managers: List[CubeManager]):
        now_s = time.time()
        
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
        await self.guess_tiles(publish_queue, word_tiles_list, player)

    async def guess_tiles(self, publish_queue, word_tiles_list, player: int):
        self.last_guess_tiles = word_tiles_list
        await guess_last_tiles(publish_queue, player)

    async def load_rack(self, publish_queue, tiles_with_letters: list[tiles.Tile], player: int):
        await cube_managers[player].load_rack(publish_queue, tiles_with_letters)

        if self.last_tiles_with_letters != tiles_with_letters:
            # Some of the tiles changed. Make a guess, just in case one of them
            # was in our last guess (which is overkill).
            logging.info(f"LOAD RACK guessing")
            await guess_last_tiles(publish_queue, player)
            self.last_tiles_with_letters = tiles_with_letters

# Global managers for each player
cube_managers: List[CubeManager] = [CubeManager(player) for player in range(PLAYER_COUNT)]
# Global mapping of cube IDs to player numbers for O(1) lookup
cube_to_player: Dict[str, int] = {}
# Global guess manager
guess_manager = GuessManager()

async def _publish_letter(publish_queue, letter, cube_id):
    await publish_queue.put((f"cube/{cube_id}/letter", letter, True))

async def accept_new_letter(publish_queue, letter, tile_id, player: int):
    cube_id = cube_managers[player].tiles_to_cubes[tile_id]
    cube_managers[player].cubes_to_letters[cube_id] = letter
    await _publish_letter(publish_queue, letter, cube_id)

async def load_rack(publish_queue, tiles_with_letters: list[tiles.Tile], player: int):
    await guess_manager.load_rack(publish_queue, tiles_with_letters, player)

async def guess_tiles(publish_queue, word_tiles_list, player: int):
    await guess_manager.guess_tiles(publish_queue, word_tiles_list, player)

async def guess_word_based_on_cubes(sender: str, tag: str, publish_queue):
    await guess_manager.guess_word_based_on_cubes(sender, tag, publish_queue, cube_to_player, cube_managers)

guess_tiles_callback: Callable[[str, bool], Coroutine[None, None, None]]

def set_guess_tiles_callback(f):
    global guess_tiles_callback
    guess_tiles_callback = f

def set_start_game_callback(f):
    global start_game_callback
    start_game_callback = f

async def letter_lock(publish_queue, locked_on: bool, tile_id: str) -> None:
    for player in range(len(cube_managers)):
        cube_id = cube_managers[player].tiles_to_cubes[tile_id]
        await publish_queue.put((f"cube/{cube_id}/lock", "1" if locked_on else "", True))

async def guess_last_tiles(publish_queue, player: int) -> None:
    logging.info(f"guess_last_tiles last_guess_tiles {guess_manager.last_guess_tiles}")
        
    for guess in guess_manager.last_guess_tiles:
        await guess_tiles_callback(guess, True, player)

    await cube_managers[player]._mark_tiles_for_guess(publish_queue, guess_manager.last_guess_tiles)

async def flash_guess(publish_queue, tiles: list[str], player: int):
    await cube_managers[player].flash_guess(publish_queue, tiles)

async def process_cube_guess(publish_queue, topic: aiomqtt.Topic, data: str):
    logging.info(f"process_cube_guess: {topic} {data}")
    print(f"process_cube_guess: {topic} {data}")
    sender = topic.value.removeprefix("cube/nfc/")
    await publish_queue.put((f"game/nfc/{sender}", data, True))
    if data in START_GAME_CUBES:
        await start_game_callback()
        return
    await guess_word_based_on_cubes(sender, data, publish_queue)

def read_data(f) -> List[str]:
    """Read all data from file."""
    data = f.readlines()
    return [l.strip() for l in data]

def read_data_for_player(f, player: int) -> List[str]:
    """Read data from file, returning the appropriate section for the given player."""
    data = f.readlines()
    data = [l.strip() for l in data]
    start_idx = player * tiles.MAX_LETTERS
    end_idx = start_idx + tiles.MAX_LETTERS
    return data[start_idx:end_idx]

async def init(subscribe_client, cubes_file, tags_file):
    await subscribe_client.subscribe("cube/nfc/#")
    
    all_cubes = [str(i) for i in range(1, 7)]

    # Read all data first
    with open(tags_file) as tags_f:
        all_tags = read_data(tags_f)
    
    # Clear and rebuild the global cube_to_player mapping
    cube_to_player.clear()
    
    # Initialize managers for each player
    for player, manager in enumerate(cube_managers):
        # Get player-specific data
        start_idx = player * tiles.MAX_LETTERS
        end_idx = start_idx + tiles.MAX_LETTERS
        cubes = all_cubes[start_idx:end_idx]
        tags = all_tags[start_idx:end_idx]
        manager.tags_to_cubes = {tag: cube for cube, tag in zip(cubes, tags)}
        manager.cube_list = cubes  # Store ordered list of cubes
        
        # Add to global cube_to_player mapping
        for cube in cubes:
            cube_to_player[cube] = player
            
        manager._initialize_arrays()

async def handle_mqtt_message(publish_queue, message):
    await process_cube_guess(publish_queue, message.topic, message.payload.decode())

async def good_guess(publish_queue, tiles: list[str], player: int):
    cube_managers[player].border_color = "0x07E0"
    await flash_guess(publish_queue, tiles, player)

async def old_guess(publish_queue, tiles: list[str], player: int):
    cube_managers[player].border_color = "0xFFE0"

async def bad_guess(publish_queue, tiles: list[str], player: int):
    cube_managers[player].border_color = "0xFFFF"
