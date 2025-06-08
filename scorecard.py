from enum import Enum
import logging
import os
from pathlib import Path

import dictionary
import tiles

SCRABBLE_LETTER_SCORES = {
    'A': 1, 'B': 3, 'C': 3, 'D': 2, 'E': 1, 'F': 4, 'G': 2, 'H': 4, 'I': 1, 'J': 8, 'K': 5, 'L': 1, 'M': 3,
    'N': 1, 'O': 1, 'P': 3, 'Q': 10, 'R': 1, 'S': 1, 'T': 1, 'U': 1, 'V': 4, 'W': 4, 'X': 8, 'Y': 4, 'Z': 10
}

Play = Enum("Play", ["GOOD", "MISSING_LETTERS", "DUPE_WORD", "BAD_WORD"])

class ScoreCard:
    def __init__(self, player_rack:tiles.Rack, dictionary: dictionary.Dictionary) -> None:
        self._previous_guesses: set[tuple[int, str]] = set()
        self.staged_guesses: set[str] = set()
        self.possible_guessed_words: set[str] = set()
        self.remaining_previous_guesses: set[str] = set() # After possible have been removed
        self.player_rack = player_rack
        self.dictionary = dictionary

    def calculate_score(self, word: str) -> int:
        return len(word) + (10 if len(word) == tiles.MAX_LETTERS else 0)

    def is_old_guess(self, guess: str) -> bool:
        return guess in self.staged_guesses

    def add_staged_guess(self, guess: str) -> None:
        self.staged_guesses.add(guess)

    def is_good_guess(self, guess: str) -> bool:
        if not self.dictionary.is_word(guess):
            return False

        if guess in self.staged_guesses:
            return False

        return True

    def add_guess(self, guess: str, player: int) -> None:
        logging.info(f"guessing {guess}")
        self.player_rack.guess(guess)
        self._previous_guesses.add((player, guess))
        self.possible_guessed_words.add(guess)

    def update_previous_guesses(self) -> None:
        words = [word for _, word in self._previous_guesses]
        self.possible_guessed_words = set(
            [word for word in words
             if not self.player_rack.missing_letters(word)])
        self.remaining_previous_guesses = set(words) - self.possible_guessed_words

    def get_previous_guesses(self) -> list[str]:
        return sorted([word for _, word in self._previous_guesses])

    def get_remaining_previous_guesses(self) -> list[str]:
        return sorted(list(self.remaining_previous_guesses))
