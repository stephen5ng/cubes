from typing import List
from game.game_state import Game

def assert_player_started(game: Game, player: int = 0):
    """Assert that a specific player has started."""
    assert game.racks[player].running, f"Player {player} rack is not running"
    assert game.scores[player].score >= 0, f"Player {player} score not initialized"

def assert_score_matches(game: Game, player: int, expected_score: int):
    """Assert that a player's score matches the expected value."""
    actual_score = game.scores[player].score
    assert actual_score == expected_score, f"Player {player} score mismatch: expected {expected_score}, got {actual_score}"

def assert_word_in_guesses(game: Game, word: str) -> None:
    """Assert word appears in either possible or remaining previous guesses display."""
    guesses_mgr = game.guesses_manager
    possible_guesses = guesses_mgr.previous_guesses_display.previous_guesses
    remaining_guesses = guesses_mgr.remaining_previous_guesses_display.remaining_guesses
    all_guesses = possible_guesses + remaining_guesses

    assert word in all_guesses, (
        f"Word '{word}' not found in previous guesses.\n"
        f"  Possible words (rack complete): {possible_guesses}\n"
        f"  Remaining words (rack incomplete): {remaining_guesses}"
    )

def assert_letter_active(game: Game):
    """Assert that a letter is currently falling."""
    assert game.letter.letter is not None, "No letter is active"
    assert game.letter.falling, "Letter is not falling"
