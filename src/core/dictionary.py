import logging
import random
from typing import Callable

from core import tiles
from core.tiles import Rack

def _sort_word(word):
    return "".join(sorted(word))

class Dictionary:
    @classmethod
    def from_words(
        cls,
        words: list[str],
        bingos: list[str] = None,
        min_letters: int = 3,
        max_letters: int = 6
    ) -> 'Dictionary':
        """Create a dictionary from word lists without file I/O."""
        d = cls(min_letters, max_letters)
        for word in words:
            word_upper = word.upper()
            if min_letters <= len(word_upper) <= max_letters:
                d._all_words.add(word_upper)
                
        if bingos is None:
            d._bingos = [w for w in d._all_words if len(w) == max_letters]
        else:
            d._bingos = [b.upper() for b in bingos if len(b) >= min_letters]
        return d

    def __init__(self, min_letters: int, max_letters: int, open: Callable=open) -> None:
        self._open = open
        self._bingos: list[str] = []
        self._all_words: set[str] = set()
        self._min_letters = min_letters
        self._max_letters = max_letters
        self._random_state = random.getstate()
        random.seed(1)

    def read(self, dictionary_file: str, bingos_file: str) -> None:
        with self._open(dictionary_file, "r") as f:
            for line in f:
                word = line.strip().upper()
                if len(word) < self._min_letters or len(word) > self._max_letters:
                    continue
                self._all_words.add(word)

        with self._open(bingos_file, "r") as f:
            for line in f:
                converted = line.strip().upper()
                if converted:
                    self._bingos.append(line.strip().upper())

    def get_rack(self) -> Rack:
        random.setstate(self._random_state)
        bingo = random.choice(self._bingos)
        self._random_state = random.getstate()
        # bingo = "AAAAAA"
        print(f"initial bingo: ---------- {bingo} --------")
        return Rack(_sort_word(bingo))

    def is_word(self, word: str) -> bool:
        return word in self._all_words
