from enum import Enum
import logging
import os
from pathlib import Path

import dictionary
from blockwords.core import tiles

SCRABBLE_LETTER_SCORES = {
    'A': 1, 'B': 3, 'C': 3, 'D': 2, 'E': 1, 'F': 4, 'G': 2, 'H': 4, 'I': 1, 'J': 8, 'K': 5, 'L': 1, 'M': 3,
    'N': 1, 'O': 1, 'P': 3, 'Q': 10, 'R': 1, 'S': 1, 'T': 1, 'U': 1, 'V': 4, 'W': 4, 'X': 8, 'Y': 4, 'Z': 10
}

Play = Enum("Play", ["GOOD", "MISSING_LETTERS", "DUPE_WORD", "BAD_WORD"])

class ScoreCard:
    def __init__(self, player_rack:tiles.Rack, dictionary: dictionary.Dictionary) -> None:
        self.guesses: set[tuple[int, str]] = set()  # (player, word) tuples
        self.staged_words: set[str] = set()  # Words being staged before final acceptance
        self.possible_words: set[str] = set()  # Words that can still be made with current letters
        self.remaining_words: set[str] = set()  # Words that can't be made with current letters
        self.player_rack = player_rack
        self.dictionary = dictionary

    def calculate_score(self, word: str) -> int:
        return len(word) + (10 if len(word) == tiles.MAX_LETTERS else 0)

    def is_old_guess(self, guess: str) -> bool:
        return guess in self.staged_words

    def add_staged_guess(self, guess: str) -> None:
        self.staged_words.add(guess)

    def is_good_guess(self, guess: str) -> bool:
        return self.dictionary.is_word(guess) and guess not in self.staged_words

    def add_guess(self, guess: str, player: int) -> None:
        logging.info(f"guessing {guess}")
        self.player_rack.guess(guess)
        self.guesses.add((player, guess))
        self.update_previous_guesses()

    def update_previous_guesses(self) -> None:
        self.possible_words = {word for _, word in self.guesses 
                             if not self.player_rack.missing_letters(word)}
        self.remaining_words = {word for _, word in self.guesses} - self.possible_words

    def get_previous_guesses(self) -> list[str]:
        return sorted(list(self.possible_words))

    def get_remaining_previous_guesses(self) -> list[str]:
        return sorted(list(self.remaining_words))
