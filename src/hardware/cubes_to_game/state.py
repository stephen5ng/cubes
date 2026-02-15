"""Global state management for the cubes-to-game system.

This module contains all mutable global state and provides setter/getter
functions for clean encapsulation. It has no dependencies on other cubes_to_game
modules to avoid circular imports.

WHEN TO USE GLOBAL STATE (this module):
- State that spans multiple cube sets (e.g., game_running affects both players)
- State needed by coordination layer across async boundaries
- State that tests need to inject/replace (e.g., manager instances)
- Configuration that can be overridden at runtime (e.g., ABC_COUNTDOWN_DELAY_MS)

WHEN NOT TO USE GLOBAL STATE:
- Per-player cube state → use CubeSetManager
- Per-player ABC countdown state → use ABCManager
- Transient function-local state → use local variables
- Configuration that never changes → use config.game_config

STATE CATEGORIES:

1. Game Lifecycle State:
   - _game_running: Whether any game is currently active
   - _started_players: Set of players (0, 1) who have started their games
   - _started_cube_sets: Set of cube sets (0, 1) that completed ABC countdown

2. Manager Instances (for test injection):
   - cube_set_managers: List of CubeSetManager instances (one per player)
   - abc_manager: ABCManager instance for countdown sequences

3. Callback Functions (injected by game logic layer):
   - guess_tiles_callback: Called when player makes a guess
   - start_game_callback: Called when player completes ABC countdown

4. Hardware Mappings:
   - cube_to_cube_set: Maps cube ID (e.g., "1") to cube_set_id (0 or 1)
   - locked_cubes: Tracks which cube is currently locked per player

5. Guess Tracking State:
   - last_guess_tiles: List of tile IDs in the most recent guess
   - last_tiles_with_letters: List of tiles last loaded to rack

ARCHITECTURE NOTES:
- This module has NO imports from other cubes_to_game modules (prevents circular deps)
- Manager instances are created in coordination.py but stored here for shared access
- Tests can replace manager instances and have all code see the replacement
- All state mutations go through setter functions for debuggability
"""

import logging
from typing import Callable, Coroutine, Dict

from config import game_config

# ABC countdown delay - use config value by default, but allow override for replay
ABC_COUNTDOWN_DELAY_MS = game_config.ABC_COUNTDOWN_DELAY_MS


def set_abc_countdown_delay(delay_ms: int):
    """Set the ABC countdown delay for replay compatibility."""
    global ABC_COUNTDOWN_DELAY_MS
    ABC_COUNTDOWN_DELAY_MS = delay_ms


# Game state tracking
_game_running = False

# Flag to track if game_on mode game has ended (should not re-activate ABC)
game_on_mode_ended = False

# ABC countdown tracking - which cube sets (0, 1) completed the ABC sequence
_started_cube_sets = set()

# Game play tracking - which players (0, 1) have started their games
_started_players = set()


def set_game_running(running: bool) -> None:
    """Set the current game running state.

    Args:
        running: True if a game is active, False otherwise

    Note:
        Clears the game_on_mode_ended flag when a new game starts.
    """
    global _game_running, game_on_mode_ended
    _game_running = running
    # Clear game_on_ended flag when a new game starts
    if running:
        game_on_mode_ended = False
    logging.info(f"Game running state set to: {running}")


def get_game_running() -> bool:
    """Get the current game running state."""
    return _game_running


def set_game_end_time(now_ms: int, min_win_score: int) -> None:
    """Set game running state to false when game ends.

    Args:
        now_ms: Current timestamp in milliseconds
        min_win_score: Minimum score to win (0 for normal mode, >0 for game_on mode)

    Behavior:
        - In game_on mode (min_win_score > 0): Sets flag to prevent ABC re-activation
        - In normal mode (min_win_score = 0): ABC remains available for next game
    """
    global _game_running, game_on_mode_ended
    _game_running = False
    # In game_on mode (min_win_score > 0), set flag to prevent ABC from being re-activated
    # In normal mode, ABC should remain available so players can start a new game
    if min_win_score > 0:
        game_on_mode_ended = True
        if abc_manager:
            abc_manager.reset()
        logging.info(f"Game ended in game_on mode at {now_ms} - ABC disabled")
    else:
        logging.info(f"Game ended at {now_ms} - ABC enabled for next game")


def reset_game_on_mode_ended() -> None:
    """Reset the game_on mode ended flag (for testing and initialization)."""
    global game_on_mode_ended
    game_on_mode_ended = False


def has_player_started_game(player: int) -> bool:
    """Check if a specific player has started their game."""
    return player in _started_players


def add_player_started(player: int) -> None:
    """Mark a player as having started their game."""
    _started_players.add(player)


def reset_player_started_state() -> None:
    """Reset the set of players who have started their games."""
    global _started_players
    _started_players = set()


def reset_started_cube_sets() -> None:
    """Reset the set of cube sets that completed ABC countdown."""
    global _started_cube_sets
    _started_cube_sets = set()


def add_started_cube_set(cube_set_id: int) -> None:
    """Mark a cube set as having completed the ABC sequence.

    Args:
        cube_set_id: The cube set ID (0 or 1) that completed ABC
    """
    _started_cube_sets.add(cube_set_id)


def get_started_cube_sets() -> list:
    """Get list of cube sets that completed ABC countdown.

    Returns:
        List of cube_set_ids (0, 1) that completed ABC sequence
    """
    return list(_started_cube_sets)


# Cube-to-cube-set mapping for O(1) lookup
cube_to_cube_set: Dict[str, int] = {}


# Letter lock tracking (which cube is currently locked per player)
locked_cubes = {}


# Manager instances - initialized by coordination module but stored here for shared access
# This allows tests to replace these instances and have all code see the replacement
cube_set_managers = None  # Will be set by coordination.init()
abc_manager = None  # Will be set by coordination module

# Guess tracking state (formerly in GuessManager)
last_guess_tiles = []  # List of tile IDs in the last guess
last_tiles_with_letters = []  # List of tiles last loaded to rack


# Callback functions (injected by game logic)
guess_tiles_callback: Callable[[str, bool], Coroutine[None, None, None]] = None
remove_highlight_callback: Callable[[list[str], int], Coroutine[None, None, None]] = None
start_game_callback: Callable = None


def set_guess_tiles_callback(f):
    """Register the callback for when tiles are guessed."""
    global guess_tiles_callback
    guess_tiles_callback = f


def set_remove_highlight_callback(f):
    """Register the callback for when highlights should be removed."""
    global remove_highlight_callback
    remove_highlight_callback = f


def set_start_game_callback(f):
    """Register the callback for when game starts."""
    global start_game_callback
    start_game_callback = f
