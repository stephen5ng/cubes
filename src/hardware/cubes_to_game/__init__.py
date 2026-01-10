"""BlockWords cubes-to-game hardware interface.

This module provides the interface between physical cube hardware and game logic,
managing cube state, ABC countdown sequences, and guess validation.
"""

# Re-export public API from coordination module
from .coordination import (
    # Initialization
    init,
    # Letter and tile management
    accept_new_letter,
    load_rack,
    guess_tiles,
    guess_last_tiles,
    flash_guess,
    # Letter lock management
    letter_lock,
    unlock_all_letters,
    # Bulk operations
    clear_all_borders,
    clear_all_letters,
    clear_remaining_abc_cubes,
    # ABC start management
    activate_abc_start_if_ready,
    is_any_player_in_countdown,
    check_countdown_completion,
    # Guess feedback
    good_guess,
    old_guess,
    bad_guess,
    # MQTT handling
    handle_mqtt_message,
)

# Re-export state management functions and variables
from .state import (
    set_abc_countdown_delay,
    set_game_running,
    get_game_running,
    set_game_end_time,
    has_player_started_game,
    add_player_started,
    reset_player_started_state,
    reset_started_cube_sets,
    add_started_cube_set,
    get_started_cube_sets,
    set_guess_tiles_callback,
    set_start_game_callback,
    # Global state variables (for direct access)
    ABC_COUNTDOWN_DELAY_MS,
    cube_to_cube_set,
    locked_cubes,
)

# Import state module for dynamic attribute access
from . import state as _state

# Re-export classes for testing and advanced usage
from .cube_set_manager import CubeSetManager, GuessManager
from .abc_manager import ABCManager


# Dynamic attribute access for managers - allows tests to get them properly
def __getattr__(name):
    """Dynamically look up manager instances from state module."""
    if name in ('cube_set_managers', 'abc_manager', 'guess_manager'):
        return getattr(_state, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    # Initialization
    'init',
    # Letter and tile management
    'accept_new_letter',
    'load_rack',
    'guess_tiles',
    'guess_last_tiles',
    'flash_guess',
    # Letter lock management
    'letter_lock',
    'unlock_all_letters',
    # Bulk operations
    'clear_all_borders',
    'clear_all_letters',
    'clear_remaining_abc_cubes',
    # ABC start management
    'activate_abc_start_if_ready',
    'is_any_player_in_countdown',
    'check_countdown_completion',
    # Guess feedback
    'good_guess',
    'old_guess',
    'bad_guess',
    # MQTT handling
    'handle_mqtt_message',
    # Manager instances
    'cube_set_managers',
    'abc_manager',
    'guess_manager',
    # Manager classes (for testing and advanced usage)
    'CubeSetManager',
    'GuessManager',
    'ABCManager',
    # State management
    'set_abc_countdown_delay',
    'set_game_running',
    'get_game_running',
    'set_game_end_time',
    'has_player_started_game',
    'add_player_started',
    'reset_player_started_state',
    'reset_started_cube_sets',
    'add_started_cube_set',
    'get_started_cube_sets',
    'set_guess_tiles_callback',
    'set_start_game_callback',
    'ABC_COUNTDOWN_DELAY_MS',
    'cube_to_cube_set',
    'locked_cubes',
]
