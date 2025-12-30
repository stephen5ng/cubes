from enum import Enum
import logging
import os
from pathlib import Path

from core import config
from core import dictionary
from core import tiles

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
        return len(word) + (10 if len(word) == config.MAX_LETTERS else 0)

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
