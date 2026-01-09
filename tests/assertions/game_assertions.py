from game.game_state import Game

def assert_player_started(game: Game, player: int = 0):
    """Assert that a specific player has started."""
    assert game.racks[player].running, f"Player {player} rack is not running"
    assert game.scores[player].score >= 0, f"Player {player} score not initialized"

def assert_score_matches(game: Game, player: int, expected_score: int):
    """Assert that a player's score matches the expected value."""
    actual_score = game.scores[player].score
    assert actual_score == expected_score, f"Player {player} score mismatch: expected {expected_score}, got {actual_score}"

def assert_word_in_guesses(game: Game, word: str):
    """Assert that a word is in the previous guesses list."""
    # Guesses are tracked in guesses_manager
    guesses = [g.word for g in game.guesses_manager.guesses]
    assert word in guesses, f"Word '{word}' not found in previous guesses: {guesses}"

def assert_letter_active(game: Game):
    """Assert that a letter is currently falling."""
    assert game.letter.letter is not None, "No letter is active"
    assert game.letter.falling, "Letter is not falling"
