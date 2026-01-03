"""Global state management for the cubes-to-game system.

This module contains all mutable global state and provides setter/getter
functions for clean encapsulation. It has no dependencies on other cubes_to_game
modules to avoid circular imports.
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

# ABC countdown tracking - which cube sets (0, 1) completed the ABC sequence
_started_cube_sets = set()

# Game play tracking - which players (0, 1) have started their games
_started_players = set()


def set_game_running(running: bool) -> None:
    """Set the current game running state."""
    global _game_running
    _game_running = running
    logging.info(f"Game running state set to: {running}")


def get_game_running() -> bool:
    """Get the current game running state."""
    return _game_running


def set_game_end_time(now_ms: int) -> None:
    """Set game running state to false when game ends."""
    global _game_running
    _game_running = False
    logging.info(f"Game ended at {now_ms}")


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
guess_manager = None  # Will be set by coordination module


# Callback functions (injected by game logic)
guess_tiles_callback: Callable[[str, bool], Coroutine[None, None, None]] = None
start_game_callback: Callable = None


def set_guess_tiles_callback(f):
    """Register the callback for when tiles are guessed."""
    global guess_tiles_callback
    guess_tiles_callback = f


def set_start_game_callback(f):
    """Register the callback for when game starts."""
    global start_game_callback
    start_game_callback = f
