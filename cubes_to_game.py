#!/usr/bin/env python3

import aiomqtt
import asyncio
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


# Game state tracking
_game_running = False
_game_started_players = set()  # Set of players who have started their games

class ABCManager:
    """Manages ABC sequence and countdown logic."""
    
    def __init__(self):
        # ABC sequence state
        self.abc_start_active = False
        self.player_abc_cubes = {}  # Maps player number to their ABC cube assignments
        
        # Countdown state
        self.player_countdown_active = {}  # Track which players are in countdown phase
        self.global_countdown_schedule = []  # List of (time, replacement_type)
        self.countdown_complete_time = None  # When the global countdown will complete
    
    def reset(self):
        """Reset all ABC/countdown state."""
        self.abc_start_active = False
        self.player_abc_cubes = {}
        self.player_countdown_active = {}
        self.global_countdown_schedule = []
        self.countdown_complete_time = None
    
    def is_any_player_in_countdown(self) -> bool:
        """Check if any player is currently in countdown phase."""
        return bool(self.player_countdown_active)
    
    async def assign_abc_letters_to_available_players(self, publish_queue, now_ms: int) -> None:
        """Assign ABC letters to players who have enough cubes but don't have ABC assignments yet."""
        self.abc_start_active = True
        letters = ["A", "B", "C"]
        for manager in cube_managers:
            # Skip if this player already has ABC assignments
            if manager.player_number in self.player_abc_cubes:
                continue
                
            player_abc_cubes = _find_non_touching_cubes_for_player(manager)
            if len(player_abc_cubes) >= 3:
                self.player_abc_cubes[manager.player_number] = {
                    "A": player_abc_cubes[0],
                    "B": player_abc_cubes[1], 
                    "C": player_abc_cubes[2]
                }
                for i, letter in enumerate(letters):
                    cube_id = player_abc_cubes[i]
                    await _publish_letter(publish_queue, letter, cube_id, now_ms)
                    print(f"activating abc: {cube_id}: {letter}")

    async def activate_abc_start_sequence(self, publish_queue, now_ms: int) -> None:
        """Activate the ABC sequence start system."""
        # Check if any player has at least 3 cubes with neighbor reports
        has_enough_cubes = False
        for manager in cube_managers:
            available_cubes = [cube for cube in manager.cube_list if cube in manager.cubes_to_neighbors]
            if len(available_cubes) >= 3:
                has_enough_cubes = True
                break
        
        if not has_enough_cubes:
            return  # Wait until at least one player has enough cubes
            
        await self.assign_abc_letters_to_available_players(publish_queue, now_ms)

    async def check_abc_sequence_complete(self):
        """Check if A-B-C cubes are placed in sequence. Returns player number if complete, None otherwise."""

        if not self.abc_start_active:
            return None
        # Check all cube managers for ABC sequence using the stored assignments
        for manager in cube_managers:
            print(f"checking abc sequence: {manager.player_number}: {self.player_abc_cubes} {self.player_countdown_active} ")        
            player_num = manager.player_number
            if (player_num in self.player_abc_cubes and 
                player_num not in self.player_countdown_active):
                # Get the specific cubes that were assigned ABC for this player
                player_abc = self.player_abc_cubes[player_num]
                cube_a = player_abc["A"]
                cube_b = player_abc["B"] 
                cube_c = player_abc["C"]
                
                logging.info(f"ABC check: manager {player_num} checking {cube_a}->{cube_b}->{cube_c} in chain={manager.cube_chain}")
                print(f"ABC check: manager {player_num} checking {cube_a}->{cube_b}->{cube_c} in chain={manager.cube_chain}")
                
                # Check if A->B->C chain exists for this player's assigned ABC cubes
                if (cube_a in manager.cube_chain and 
                    manager.cube_chain[cube_a] == cube_b and
                    cube_b in manager.cube_chain and 
                    manager.cube_chain[cube_b] == cube_c):
                    print(f"ABC sequence complete for player {player_num}!")
                    logging.info(f"ABC sequence complete for player {player_num}!")
                    return player_num
        
        return None

    async def execute_letter_stage_for_player(self, publish_queue, player: int, stage_type: str, now_ms: int) -> None:
        """Execute a letter stage for a specific player."""
        abc_cubes = self.player_abc_cubes[player]
        all_player_cubes = cube_managers[player].cube_list
        abc_cube_ids = set(abc_cubes.values())
        non_abc_cubes = [cube for cube in all_player_cubes if cube not in abc_cube_ids]
        
        if stage_type == 'non_abc_1' and len(non_abc_cubes) > 0:
            await publish_queue.put((f"cube/{non_abc_cubes[0]}/letter", "?", True, now_ms))
        elif stage_type == 'non_abc_2' and len(non_abc_cubes) > 1:
            await publish_queue.put((f"cube/{non_abc_cubes[1]}/letter", "?", True, now_ms))
        elif stage_type == 'non_abc_3' and len(non_abc_cubes) > 2:
            await publish_queue.put((f"cube/{non_abc_cubes[2]}/letter", "?", True, now_ms))
        elif stage_type == 'A':
            await publish_queue.put((f"cube/{abc_cubes['A']}/letter", "?", True, now_ms))
        elif stage_type == 'B':
            await publish_queue.put((f"cube/{abc_cubes['B']}/letter", "?", True, now_ms))
        elif stage_type == 'C':
            await publish_queue.put((f"cube/{abc_cubes['C']}/letter", "?", True, now_ms))

    async def apply_past_letter_stages(self, publish_queue, player: int, now_ms: int) -> None:
        """Apply letter stages that have already occurred for a player joining mid-countdown."""
        # Apply all stages that should have already happened
        for stage_time, stage_type in self.global_countdown_schedule:
            if stage_time < now_ms:  # This stage is in the past
                await self.execute_letter_stage_for_player(publish_queue, player, stage_type, now_ms)

    async def execute_countdown_stage(self, publish_queue, stage_type: str, now_ms: int) -> None:
        """Execute a countdown stage for all active countdown players."""
        for player in self.player_countdown_active:
            await self.execute_letter_stage_for_player(publish_queue, player, stage_type, now_ms)

    async def sync_player_with_countdown(self, publish_queue, player: int, now_ms: int) -> None:
        """Sync a player's cubes with the existing countdown animation.
        
        This function makes the second player's cubes change to '?' in sync with 
        the global letter-by-letter countdown progression.
        """        
        self.player_countdown_active[player] = True
        
        logging.info(f"Player {player} joining countdown - will sync with global letter progression")
        print(f"Player {player} joining countdown - synchronized start")
        
        await self.apply_past_letter_stages(publish_queue, player, now_ms)

    async def start_abc_countdown(self, publish_queue, player: int, now_ms: int) -> None:
        """Start the global ABC countdown sequence."""
        self.player_countdown_active[player] = True
        
        logging.info(f"ABC sequence complete for player {player}! Starting global countdown")
        print(f"ABC sequence complete for player {player}! Starting countdown")
        
        # Create global countdown schedule: 3 non-ABC stages, then A, B, C (500ms intervals)
        stages = ['non_abc_1', 'non_abc_2', 'non_abc_3', 'A', 'B', 'C']
        self.global_countdown_schedule = [(now_ms + i * 500, stage) for i, stage in enumerate(stages)]
        
        # Game will start 0.5s after the last replacement
        self.countdown_complete_time = now_ms + len(stages) * 500

    async def handle_abc_completion(self, publish_queue, completed_player: int, now_ms: int) -> None:
        """Handle when a player completes their ABC sequence.
        
        If someone is already in countdown, join them. Otherwise start a new countdown.
        """
        if self.is_any_player_in_countdown():
            logging.info(f"Player {completed_player} joining active countdown")
            await self.sync_player_with_countdown(publish_queue, completed_player, now_ms)
        else:
            logging.info(f"Player {completed_player} starting new countdown")
            await self.start_abc_countdown(publish_queue, completed_player, now_ms)

    async def check_countdown_completion(self, publish_queue, now_ms: int) -> list:
        """Check if countdown stages need to be executed and if countdown has completed.
        Returns incidents for any countdown replacements that occurred."""
        incidents = []
        
        # Execute any pending global countdown stages
        if self.global_countdown_schedule:
            remaining_stages = []
            for stage_time, stage_type in self.global_countdown_schedule:
                if now_ms >= stage_time:
                    # Execute this stage for all active countdown players
                    await self.execute_countdown_stage(publish_queue, stage_type, now_ms)
                    incidents.append(f"abc_countdown_replacement: {stage_type}")
                else:
                    remaining_stages.append((stage_time, stage_type))
            self.global_countdown_schedule = remaining_stages
        
        # Check for completed countdowns
        completed_players = []
        if self.countdown_complete_time and now_ms >= self.countdown_complete_time:
            # All players in countdown complete at the same time
            for player in list(self.player_countdown_active.keys()):
                logging.info(f"ABC countdown complete for player {player}! Starting game at {now_ms}")
                print(f"ABC countdown complete for player {player}! Starting game")
                
                _game_started_players.add(player)
                completed_players.append(player)
                
                await start_game_callback(True, self.countdown_complete_time, player)
            abc_manager.reset()
        
        # If any player completed countdown, clean up countdown state
        if completed_players:
            # Clear global countdown state
            self.global_countdown_schedule = []
            self.countdown_complete_time = None
        
        return incidents

# Global ABC manager instance
abc_manager = ABCManager()
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
        # Only load letters if this player has started their game
        if self.player_number not in _game_started_players:
            logging.info(f"LOAD RACK: Player {self.player_number} game not started, skipping letter loading")
            return
            
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
        # Only draw borders when this player's game is running
        if self.player_number not in _game_started_players:
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
    """Set game running state to false when game ends."""
    global _game_running
    _game_running = False
    logging.info(f"Game ended at {now_ms}")

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

async def clear_remaining_abc_cubes(publish_queue, now_ms: int) -> None:
    """Clear ABC cubes for any remaining players in abc_manager.player_abc_cubes."""
    for player_num in list(abc_manager.player_abc_cubes.keys()):
        # Clear ABC letters for this player
        abc_assignments = abc_manager.player_abc_cubes[player_num]
        for _, cube_id in abc_assignments.items():
            await publish_queue.put((f"cube/{cube_id}/letter", " ", True, now_ms))
        # Remove this player from ABC tracking
        del abc_manager.player_abc_cubes[player_num]

def set_game_running(running: bool) -> None:
    """Set the current game running state."""
    global _game_running
    _game_running = running
    logging.info(f"Game running state set to: {running}")

def _find_non_touching_cubes_for_player(manager) -> List[str]:
    """Find 3 non-touching cubes for a specific player."""
    available_cubes = [cube for cube in manager.cube_list if cube in manager.cubes_to_neighbors]
    
    if len(available_cubes) < 3:
        return available_cubes  # Return what we have, even if less than 3
    print(f"manager cube chain: {manager.cube_chain}")
    selected_cubes = []
    for cube in available_cubes:
        if len(selected_cubes) >= 3:
            break
        print(f"checking cube {cube}")
        # Check if this cube touches any already selected cube
        is_touching = any(
            manager.cube_chain.get(cube) == selected or 
            manager.cube_chain.get(selected) == cube
            for selected in selected_cubes
        )

        if not is_touching:
            selected_cubes.append(cube)

    print(f"selected: {selected_cubes}")
    return selected_cubes[:3]

def _has_received_initial_neighbor_reports() -> bool:
    """Check if we've received at least some neighbor reports from cubes."""
    for manager in cube_managers:
        if manager.cubes_to_neighbors:  # If any manager has received neighbor reports
            return True
    return False

async def activate_abc_start_if_ready(publish_queue, now_ms: int) -> None:
    """Activate ABC start sequence if conditions are met and assign letters to new players."""
    if not _game_running and _has_received_initial_neighbor_reports():
        await abc_manager.assign_abc_letters_to_available_players(publish_queue, now_ms)

def has_player_started_game(player: int) -> bool:
    """Check if a specific player has started their game."""
    return player in _game_started_players

def is_any_player_in_countdown() -> bool:
    """Check if any player is currently in countdown phase."""
    return abc_manager.is_any_player_in_countdown()

def _get_all_cube_ids() -> List[str]:
    """Get all valid cube IDs (1-6 for Player 0, 11-16 for Player 1)."""
    return [str(i) for i in range(1, 7)] + [str(i) for i in range(11, 17)]

async def init(subscribe_client):
    # Subscribe to direct neighbor topics only
    await subscribe_client.subscribe("cube/right/#")
    
    all_cubes = _get_all_cube_ids()

    # Clear and rebuild the global cube_to_player mapping
    cube_to_player.clear()
    
    # Initialize player game states
    global _game_started_players
    _game_started_players.clear()
    
    # Reset ABC manager state
    abc_manager.reset()
    
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
            if abc_manager.abc_start_active:
                completed_player = await abc_manager.check_abc_sequence_complete()
                if completed_player is not None:
                    await abc_manager.handle_abc_completion(publish_queue, completed_player, now_ms)
            
            # Countdown completion is polled from the main loop, not per-message
        return


async def good_guess(publish_queue, tiles: list[str], player: int, now_ms: int):
    cube_managers[player].border_color = "0x07E0"
    await flash_guess(publish_queue, tiles, player, now_ms)

async def old_guess(publish_queue, tiles: list[str], player: int):
    cube_managers[player].border_color = "0xFFE0"

async def bad_guess(publish_queue, tiles: list[str], player: int):
    cube_managers[player].border_color = "0xFFFF"
