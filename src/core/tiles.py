from collections import Counter
from dataclasses import dataclass
import logging
import random
from typing import Sequence

from config import game_config

MAX_LETTERS = game_config.MAX_LETTERS
MIN_LETTERS = game_config.MIN_LETTERS

SCRABBLE_LETTER_FREQUENCIES = Counter({
    'A': 9, 'B': 2, 'C': 2, 'D': 4, 'E': 12, 'F': 2, 'G': 3, 'H': 2, 'I': 9, 'J': 1, 'K': 1, 'L': 4, 'M': 2,
    'N': 6, 'O': 8, 'P': 2, 'R': 6, 'S': 4, 'T': 6, 'U': 4, 'V': 2, 'W': 2, 'X': 1, 'Y': 2, 'Z': 1
})

ENGLISH_LETTER_FREQUENCIES = Counter({
    'A': 16, 'B': 4, 'C': 9, 'D': 6, 'E': 22, 'F': 4, 'G': 5, 'H': 6, 'I': 15, 'J': 1, 'K': 2, 'L': 11, 'M': 6,
    'N': 13, 'O': 14, 'P': 6, 'R': 15, 'S': 12, 'T': 14, 'U': 7, 'V': 2, 'W': 2, 'X': 1, 'Y': 4, 'Z': 1
})
FREQUENCIES = ENGLISH_LETTER_FREQUENCIES

BAG_SIZE = sum(FREQUENCIES.values())

@dataclass(unsafe_hash=True)
class Tile:
    # Class to track the cubes. Unlike Scrabble, a "tile"'s letter is mutable.

    letter: str
    id: str

def _tiles_to_letters(tiles: Sequence[Tile]) -> str:
    return ''.join(t.letter for t in tiles)

class Rack:
    def __init__(self, letters: str) -> None:
        self.random_state = random.getstate()        
        self._tiles = []
        for count, letter in enumerate(letters):
            self._tiles.append(Tile(letter, str(count)))
        self._last_guess: list[Tile]  = []
        self._next_letter = self.gen_next_letter()

    def __repr__(self) -> str:
        return (f"TILES: {self._tiles}\n" +
            f"LAST_GUESS: {self._last_guess}")

    def get_tiles(self) -> list[Tile]:
        return self._tiles

    def id_to_position(self, id: str) -> int:
        return self._tiles.index(next(t for t in self._tiles if t.id == id))

    def set_tiles(self, tiles: list[Tile]) -> None:
        self._tiles = tiles

    def last_guess(self) -> None:
        return _tiles_to_letters(self._last_guess)

    def letters_to_ids(self, letters: str) -> list[str]:
        # Create a lookup of available tiles by letter
        available_tiles = {}
        for tile in self._tiles:
            if tile.letter not in available_tiles:
                available_tiles[tile.letter] = []
            available_tiles[tile.letter].append(tile)
        
        # Build the result list
        ids = []
        for letter in letters:
            if letter in available_tiles and available_tiles[letter]:
                tile = available_tiles[letter].pop()  # Get and remove the first available tile
                ids.append(tile.id)
        return ids

    def ids_to_tiles(self, ids: list[str]) -> list[Tile]:
        tiles = []
        for an_id in ids:
            tiles.append(next(t for t in self._tiles if t.id == an_id))
        return tiles

    def ids_to_letters(self, ids: list[str]) -> str:
        return _tiles_to_letters(self.ids_to_tiles(ids))

    def guess(self, guess: str) -> None:
        logging.info(f"guess({guess})")
        self._last_guess = self.ids_to_tiles(self.letters_to_ids(guess))

    def missing_letters(self, word: str) -> str:
        rack_hash = Counter(_tiles_to_letters(self._tiles))
        word_hash = Counter(word)
        if all(word_hash[letter] <= rack_hash[letter] for letter in word):
            return ""
        else:
            return "".join([l for l in word_hash if word_hash[l] > rack_hash[l]])

    def letters(self) -> str:
        return _tiles_to_letters(self._tiles)

    def next_letter(self) -> str:
        return self._next_letter

    def gen_next_letter(self) -> str:
        c = Counter(''.join([l.letter for l in self._tiles]))
        for k in c.keys():
            c[k] *= int(BAG_SIZE / game_config.MAX_LETTERS)
        frequencies = Counter(FREQUENCIES) # make a copy
        frequencies.subtract(c)

        bag = [letter for letter, frequency in frequencies.items() for _ in range(frequency)]
        random.setstate(self.random_state)
        v =  random.choice(bag)
        self.random_state = random.getstate()
        return v

    def position_to_id(self, position: int) -> str:
        return self._tiles[position].id

    def replace_letter(self, new_letter: str, position: int) -> Tile:
        logging.info(f"\nreplace_letter() {new_letter} -> {str(self)}, new_letter: {new_letter}")
        remove_tile = self._tiles[position]

        remove_tile.letter = new_letter
        self._next_letter = self.gen_next_letter()
        logging.info(f"final: {str(self)}")
        return remove_tile
