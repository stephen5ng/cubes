"""Coordination layer for cubes-to-game system.

This module serves as the main orchestrator, tying together all other modules
and providing the public API for the cubes-to-game system.
"""

import logging
from typing import List

from config import game_config
from core import tiles

# Import our modules
from . import state
from .abc_manager import ABCManager
from .cube_set_manager import CubeSetManager

# Initialize global managers in state module for shared access
# This allows tests to replace these and have all code see the replacement
state.cube_set_managers = [CubeSetManager(cube_set_id) for cube_set_id in range(game_config.MAX_PLAYERS)]
state.abc_manager = ABCManager()

# Create module-level references for convenience (these will be exported)
cube_set_managers = state.cube_set_managers
abc_manager = state.abc_manager


# =============================================================================
# Helper Functions
# =============================================================================

async def _publish_letter(publish_queue, letter, cube_id, now_ms):
    """Publish a letter to a specific cube."""
    await publish_queue.put((f"cube/{cube_id}/letter", letter, True, now_ms))


def _get_all_cube_ids() -> List[str]:
    """Get all valid cube IDs (1-6 for Player 0, 11-16 for Player 1)."""
    return [str(i) for i in range(1, 7)] + [str(i) for i in range(11, 17)]


def _has_received_initial_neighbor_reports() -> bool:
    """Check if we've received at least some neighbor reports from cubes."""
    for manager in cube_set_managers:
        if manager.cubes_to_neighbors:  # If any manager has received neighbor reports
            return True
    return False


# =============================================================================
# Letter and Tile Management
# =============================================================================

async def accept_new_letter(publish_queue, letter, tile_id, cube_set_id: int, now_ms: int):
    """Accept a new letter into the rack."""
    cube_id = state.cube_set_managers[cube_set_id].tiles_to_cubes[tile_id]
    state.cube_set_managers[cube_set_id].cubes_to_letters[cube_id] = letter
    await _publish_letter(publish_queue, letter, cube_id, now_ms)


async def load_rack(publish_queue, tiles_with_letters: list[tiles.Tile], cube_set_id: int, player: int, now_ms: int):
    """Load rack and potentially submit a guess if tiles changed."""
    # Load the rack
    await state.cube_set_managers[cube_set_id].load_rack(
        publish_queue, tiles_with_letters, now_ms, state._started_players
    )

    # If tiles changed, re-guess in case any guessed tiles were updated
    if state.last_tiles_with_letters != tiles_with_letters:
        logging.info(f"LOAD RACK guessing")
        await guess_last_tiles(publish_queue, cube_set_id, player, now_ms)
        state.last_tiles_with_letters = tiles_with_letters


async def guess_tiles(publish_queue, word_tiles_list, cube_set_id: int, player: int, now_ms: int):
    """
    Submit a guess for tiles.

    IMPORTANT: state.last_guess_tiles is a LIST OF GUESSES (list of lists), where each inner
    list is a guess containing tile IDs. This is because multiple cube chains can form
    multiple words simultaneously.

    Example: [['1', '2', '3'], ['4', '5']] means two guesses: one with tiles 1-2-3, another with tiles 4-5.

    When iterating over state.last_guess_tiles, each iteration gives you one guess (a list of tile IDs).
    """
    previous_tiles = state.last_guess_tiles
    state.last_guess_tiles = word_tiles_list

    # Detect which chains were removed by comparing previous and current tile sets
    # Convert each chain to a sorted tuple for set comparison (order-independent)
    # Only check for removals if we had previous tiles
    if state.remove_highlight_callback and previous_tiles:
        previous_chains = {tuple(sorted(chain)) for chain in previous_tiles}
        current_chains = {tuple(sorted(chain)) for chain in word_tiles_list}
        removed_chains = previous_chains - current_chains

        # Remove highlights for chains that disappeared (if any)
        if removed_chains:
            for chain in removed_chains:
                await state.remove_highlight_callback(list(chain), player)

    # If there are any remaining chains, process them
    if word_tiles_list:
        await guess_last_tiles(publish_queue, cube_set_id, player, now_ms)


async def guess_last_tiles(publish_queue, cube_set_id: int, player: int, now_ms: int) -> None:
    """Process the last guess for a player."""
    logging.info(f"guess_last_tiles last_guess_tiles {state.last_guess_tiles}")
    for guess in state.last_guess_tiles:
        await state.guess_tiles_callback(guess, True, player, now_ms)

    await state.cube_set_managers[cube_set_id]._mark_tiles_for_guess(
        publish_queue, state.last_guess_tiles, now_ms, state._started_players
    )


async def flash_guess(publish_queue, tiles: list[str], cube_set_id: int, now_ms: int):
    """Flash tiles for a guess."""
    await state.cube_set_managers[cube_set_id].flash_guess(publish_queue, tiles, now_ms)


# =============================================================================
# Letter Lock Management
# =============================================================================

async def letter_lock(publish_queue, cube_set_id, tile_id: str | None, now_ms: int) -> bool:
    """Lock a letter for a player."""
    cube_id = state.cube_set_managers[cube_set_id].tiles_to_cubes.get(tile_id) if tile_id else None

    if last_cube_id := state.locked_cubes.get(cube_set_id, None):
        if last_cube_id == cube_id:
            return False

        # Unlock last cube
        await publish_queue.put((f"cube/{last_cube_id}/lock", None, True, now_ms))

    state.locked_cubes[cube_set_id] = cube_id
    if cube_id:
        await publish_queue.put((f"cube/{cube_id}/lock", "1", True, now_ms))
    return True


async def unlock_all_letters(publish_queue, now_ms: int) -> None:
    """Unlock all locked letters across all cube sets."""
    for cube_set_id, cube_id in state.locked_cubes.items():
        if cube_id:
            await publish_queue.put((f"cube/{cube_id}/lock", None, True, now_ms))
    state.locked_cubes.clear()


# =============================================================================
# Bulk Operations
# =============================================================================

async def clear_all_borders(publish_queue, now_ms: int) -> None:
    """Clear all borders on all cubes across all players using consolidated messaging."""
    for manager in cube_set_managers:
        for cube_id in manager.cube_list:
            # Use consolidated border protocol: ":" clears all borders
            await publish_queue.put((f"cube/{cube_id}/border", ":", True, now_ms))


async def clear_all_letters(publish_queue, now_ms: int) -> None:
    """Clear letters on all cubes across all players by setting space and retaining."""
    for manager in cube_set_managers:
        for cube_id in manager.cube_list:
            await publish_queue.put((f"cube/{cube_id}/letter", " ", True, now_ms))


async def clear_remaining_abc_cubes(publish_queue, now_ms: int) -> None:
    """Clear ABC cubes for any remaining players in state.abc_manager.player_abc_cubes."""
    for player_num in list(state.abc_manager.player_abc_cubes.keys()):
        # Clear ABC letters for this player
        abc_assignments = state.abc_manager.player_abc_cubes[player_num]
        for _, cube_id in abc_assignments.items():
            await publish_queue.put((f"cube/{cube_id}/letter", " ", True, now_ms))
        # Remove this player from ABC tracking
        del state.abc_manager.player_abc_cubes[player_num]


# =============================================================================
# ABC Start Management
# =============================================================================

async def activate_abc_start_if_ready(publish_queue, now_ms: int) -> None:
    """Activate ABC start sequence if conditions are met and assign letters to new players."""
    # Don't activate ABC if game_on mode has ended (waiting for next game via MQTT)
    if state.game_on_mode_ended:
        return

    if not state.get_game_running() and _has_received_initial_neighbor_reports():
        await state.abc_manager.assign_abc_letters_to_available_players(publish_queue, now_ms, state.cube_set_managers)


def is_any_player_in_countdown() -> bool:
    """Check if any player is currently in countdown phase."""
    return state.abc_manager.is_any_player_in_countdown()


async def check_countdown_completion(publish_queue, now_ms: int, sound_manager) -> list:
    """Check if countdown stages need to be executed and if countdown has completed.

    This is a convenience wrapper that calls ABCManager.check_countdown_completion
    with the required dependencies.

    Returns:
        List of incidents for any countdown replacements that occurred
    """
    return await state.abc_manager.check_countdown_completion(
        publish_queue, now_ms, sound_manager, state.cube_set_managers,
        state.start_game_callback
    )


# =============================================================================
# Guess Feedback
# =============================================================================

async def good_guess(publish_queue, tiles: list[str], cube_set_id: int, player: int, now_ms: int):
    """Mark a guess as good (green border)."""
    state.cube_set_managers[cube_set_id].border_color = "0x07E0"
    await flash_guess(publish_queue, tiles, cube_set_id, now_ms)


async def old_guess(publish_queue, tiles: list[str], cube_set_id: int, player: int):
    """Mark a guess as old/duplicate (yellow border)."""
    state.cube_set_managers[cube_set_id].border_color = "0xFFE0"


async def bad_guess(publish_queue, tiles: list[str], cube_set_id: int, player: int):
    """Mark a guess as bad/invalid (white border)."""
    state.cube_set_managers[cube_set_id].border_color = "0xFFFF"


# =============================================================================
# Initialization
# =============================================================================

async def init(subscribe_client):
    """Initialize the cubes-to-game system."""
    # Subscribe to direct neighbor topics only
    await subscribe_client.subscribe("cube/right/#")

    all_cubes = _get_all_cube_ids()

    # Clear and rebuild the global cube_to_cube_set mapping
    state.cube_to_cube_set.clear()

    # Initialize player game states
    state.reset_player_started_state()
    state.reset_started_cube_sets()
    state.reset_game_on_mode_ended()

    # Reset ABC manager state
    state.abc_manager.reset()

    # Initialize managers for each cube set
    for cube_set_id, manager in enumerate(cube_set_managers):
        await manager.init(all_cubes)
        # Add to global cube_to_cube_set mapping
        for cube in manager.cube_list:
            state.cube_to_cube_set[cube] = cube_set_id
    logging.info(f"INIT: cube_list p0={state.cube_set_managers[0].cube_list} p1={state.cube_set_managers[1].cube_list}")
    logging.info(f"INIT: cube_to_cube_set={state.cube_to_cube_set}")


# =============================================================================
# MQTT Message Handler
# =============================================================================

async def handle_mqtt_message(publish_queue, message, now_ms: int, sound_manager):
    """Handle incoming MQTT messages from cubes."""
    topic_str = getattr(message.topic, 'value', str(message.topic))
    payload_data = message.payload.decode() if message.payload is not None else ""
    logging.info(f"MQTT recv: topic={topic_str} payload={payload_data}")

    # Direct neighbor cube id from /cube/right/SENDER
    if topic_str.startswith("cube/right/"):
        sender_cube = topic_str.removeprefix("cube/right/")
        neighbor_cube = payload_data
        cube_set_id = state.cube_to_cube_set.get(sender_cube)
        if cube_set_id is not None:
            logging.info(f"RIGHT msg: sender={sender_cube} neighbor={neighbor_cube} cube_set={cube_set_id}")
            word_tiles_list = state.cube_set_managers[cube_set_id].process_neighbor_cube(sender_cube, neighbor_cube)
            logging.info(f"WORD_TILES (right): {word_tiles_list}")
            # In single player mode, player_id is always 0; in multi-player, cube_set_id maps to player_id
            player_id = 0 if len(state._started_players) <= 1 else cube_set_id
            await guess_tiles(publish_queue, word_tiles_list, cube_set_id, player_id, now_ms)

            # Check ABC completion after processing right-edge updates
            if state.abc_manager.abc_start_active:
                completed_player = await state.abc_manager.check_abc_sequence_complete(state.cube_set_managers)
                if completed_player is not None:
                    await state.abc_manager.handle_abc_completion(
                        publish_queue, completed_player, now_ms, sound_manager,
                        state.cube_set_managers, state.ABC_COUNTDOWN_DELAY_MS
                    )

            # Countdown completion is polled from the main loop, not per-message
        return
