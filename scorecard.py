from enum import Enum
import logging
import os
import tiles
from pathlib import Path

SCRABBLE_LETTER_SCORES = {
    'A': 1, 'B': 3, 'C': 3, 'D': 2, 'E': 1, 'F': 4, 'G': 2, 'H': 4, 'I': 1, 'J': 8, 'K': 5, 'L': 1, 'M': 3,
    'N': 1, 'O': 1, 'P': 3, 'Q': 10, 'R': 1, 'S': 1, 'T': 1, 'U': 1, 'V': 4, 'W': 4, 'X': 8, 'Y': 4, 'Z': 10
}

Play = Enum("Play", ["GOOD", "MISSING_LETTERS", "DUPE_WORD", "BAD_WORD"])

class ScoreCard:
    def __init__(self, player_rack, dictionary):
        self.previous_guesses = set()
        self.staged_guesses = set()
        self.possible_guessed_words = set()
        self.remaining_previous_guesses = set() # After possible have been removed
        self.player_rack = player_rack
        self.dictionary = dictionary

    def calculate_score(self, word):
        return len(word) + (10 if len(word) == tiles.MAX_LETTERS else 0)

    def is_old_guess(self, guess):
        return guess in self.staged_guesses

    def add_staged_guess(self, guess):
        self.staged_guesses.add(guess)

    def is_good_guess(self, guess):
        if not self.dictionary.is_word(guess):
            return False

        if guess in self.staged_guesses:
            return False

        return True

    def add_guess(self, guess):
        logging.info(f"guessing {guess}")
        self.player_rack.guess(guess)
        self.previous_guesses.add(guess)
        self.possible_guessed_words.add(guess)

    def update_previous_guesses(self):
        self.possible_guessed_words = set([word for word in self.previous_guesses if not self.player_rack.missing_letters(word)])
        self.remaining_previous_guesses = self.previous_guesses - self.possible_guessed_words

    def get_previous_guesses(self):
        return sorted(list(self.possible_guessed_words))

    def get_remaining_previous_guesses(self):
        return sorted(list(self.remaining_previous_guesses))
