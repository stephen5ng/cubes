"""Type-safe event definitions for the BlockWords game.

This module defines all game events as dataclasses with typed fields,
replacing the string-based event system with compile-time type safety.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any
from blockwords.core import tiles


class EventType(str, Enum):
    """Event type identifiers - maintains backward compatibility with string-based system."""

    # Game state events
    GAME_STAGE_GUESS = "game.stage_guess"
    GAME_OLD_GUESS = "game.old_guess"
    GAME_BAD_GUESS = "game.bad_guess"
    GAME_NEXT_TILE = "game.next_tile"
    GAME_ABORT = "game.abort"
    GAME_START_PLAYER = "game.start_player"

    # Rack/tile events
    RACK_UPDATE_RACK = "rack.update_rack"
    RACK_UPDATE_LETTER = "rack.update_letter"

    # Input events
    INPUT_ADD_GUESS = "input.add_guess"
    INPUT_UPDATE_PREVIOUS_GUESSES = "input.update_previous_guesses"
    INPUT_REMAINING_PREVIOUS_GUESSES = "input.remaining_previous_guesses"


@dataclass
class GameEvent:
    """Base class for all game events."""
    event_type: EventType


# ============================================================================
# GAME STATE EVENTS
# ============================================================================

@dataclass
class GameStageGuessEvent(GameEvent):
    """Triggered when a valid word guess is made."""
    score: int
    last_guess: str
    player: int
    now_ms: int

    def __init__(self, score: int, last_guess: str, player: int, now_ms: int):
        super().__init__(EventType.GAME_STAGE_GUESS)
        self.score = score
        self.last_guess = last_guess
        self.player = player
        self.now_ms = now_ms


@dataclass
class GameOldGuessEvent(GameEvent):
    """Triggered when a duplicate/previously guessed word is submitted."""
    old_guess: str
    player: int
    now_ms: int

    def __init__(self, old_guess: str, player: int, now_ms: int):
        super().__init__(EventType.GAME_OLD_GUESS)
        self.old_guess = old_guess
        self.player = player
        self.now_ms = now_ms


@dataclass
class GameBadGuessEvent(GameEvent):
    """Triggered when an invalid/not-in-dictionary word is guessed."""
    player: int

    def __init__(self, player: int):
        super().__init__(EventType.GAME_BAD_GUESS)
        self.player = player


@dataclass
class GameNextTileEvent(GameEvent):
    """Updates the next letter that will fall into the rack."""
    next_letter: str
    now_ms: int

    def __init__(self, next_letter: str, now_ms: int):
        super().__init__(EventType.GAME_NEXT_TILE)
        self.next_letter = next_letter
        self.now_ms = now_ms


@dataclass
class GameAbortEvent(GameEvent):
    """Aborts the current game."""

    def __init__(self):
        super().__init__(EventType.GAME_ABORT)


@dataclass
class GameStartPlayerEvent(GameEvent):
    """Starts game for a specific player (enables multi-player mode)."""
    now_ms: int
    player: int

    def __init__(self, now_ms: int, player: int):
        super().__init__(EventType.GAME_START_PLAYER)
        self.now_ms = now_ms
        self.player = player


# ============================================================================
# RACK/TILE EVENTS
# ============================================================================

@dataclass
class RackUpdateRackEvent(GameEvent):
    """Updates the entire rack display with new tiles and highlighting."""
    tiles: list[Any]  # list[tiles.Tile] - using Any to avoid circular import
    highlight_length: int
    guess_length: int
    player: int
    now_ms: int

    def __init__(self, tiles: list[Any], highlight_length: int, guess_length: int,
                 player: int, now_ms: int):
        super().__init__(EventType.RACK_UPDATE_RACK)
        self.tiles = tiles
        self.highlight_length = highlight_length
        self.guess_length = guess_length
        self.player = player
        self.now_ms = now_ms


@dataclass
class RackUpdateLetterEvent(GameEvent):
    """Updates a single tile in the rack with animation."""
    changed_tile: Any  # tiles.Tile - using Any to avoid circular import
    player: int
    now_ms: int

    def __init__(self, changed_tile: Any, player: int, now_ms: int):
        super().__init__(EventType.RACK_UPDATE_LETTER)
        self.changed_tile = changed_tile
        self.player = player
        self.now_ms = now_ms


# ============================================================================
# INPUT EVENTS
# ============================================================================

@dataclass
class InputAddGuessEvent(GameEvent):
    """Adds a new guess to the previous guesses display."""
    previous_guesses: list[str]
    guess: str
    player: int
    now_ms: int

    def __init__(self, previous_guesses: list[str], guess: str, player: int, now_ms: int):
        super().__init__(EventType.INPUT_ADD_GUESS)
        self.previous_guesses = previous_guesses
        self.guess = guess
        self.player = player
        self.now_ms = now_ms


@dataclass
class InputUpdatePreviousGuessesEvent(GameEvent):
    """Updates the list of all previous guesses made in the game."""
    previous_guesses: list[str]
    now_ms: int

    def __init__(self, previous_guesses: list[str], now_ms: int):
        super().__init__(EventType.INPUT_UPDATE_PREVIOUS_GUESSES)
        self.previous_guesses = previous_guesses
        self.now_ms = now_ms


@dataclass
class InputRemainingPreviousGuessesEvent(GameEvent):
    """Updates the display of remaining/unused previous guesses."""
    previous_guesses: list[str]
    now_ms: int

    def __init__(self, previous_guesses: list[str], now_ms: int):
        super().__init__(EventType.INPUT_REMAINING_PREVIOUS_GUESSES)
        self.previous_guesses = previous_guesses
        self.now_ms = now_ms
