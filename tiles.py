from collections import Counter
import logging
import random

MIN_LETTERS = 3
MAX_LETTERS = 6

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

def remove_letters(source_string, letters_to_remove):
    for char in letters_to_remove:
        source_string = source_string.replace(char, '', 1)
    return source_string

class Tile:
    # Class to track the cubes. Unlike Scrabble, a "tile"'s letter is mutable.

    def __init__(self, letter, id):
        self.id = id  # should be a str to match json
        self.letter = letter
        self._used_counter = 0

    def __repr__(self):
        return f"{self.id}:{self.letter}[{self._used_counter}]"

    def play(self):
        self._used_counter += 1
        return self

    def get_used_count(self):
        return self._used_counter

def _tiles_to_letters(tiles):
    return ''.join([t.letter for t in tiles])

class Rack:
    def __init__(self, letters):
        self._tiles = []
        for count, letter in enumerate(letters):
            self._tiles.append(Tile(letter, count))
        self._last_guess = []
        self._unused_tiles = self._tiles

    def __repr__(self):
        return (f"TILES: {self._tiles}\n" +
            f"LAST_GUESS: {self._last_guess}\n" +
            f"UNUSED_TILES: {self._unused_tiles}")

    def get_tiles_with_letters(self):
        rack = {}
        for tile in self._tiles:
            rack[tile.id] = tile.letter
        return rack

    def last_guess(self):
        return _tiles_to_letters(self._last_guess)

    def unused_letters(self):
        return _tiles_to_letters(self._unused_tiles)

    def display(self):
        return f"{_tiles_to_letters(self._last_guess)} {_tiles_to_letters(self._unused_tiles)}"

    def guess(self, guess):
        # Assumes all the letters of guess are in the rack.

        guess_letters = list(guess)
        self._last_guess = []
        unused_tiles = list(self._tiles)
        for guess_letter in guess_letters:
            for tile in unused_tiles:
                if guess_letter == tile.letter:
                    self._last_guess.append(tile.play())
                    unused_tiles.remove(tile)
                    break

        self._unused_letters = remove_letters(_tiles_to_letters(self._tiles), guess)
        self._unused_tiles = unused_tiles
        logging.info(f"guess({guess})")

    def missing_letters(self, word):
        rack_hash = Counter(_tiles_to_letters(self._tiles))
        word_hash = Counter(word)
        if all(word_hash[letter] <= rack_hash[letter] for letter in word):
            return ""
        else:
            return "".join([l for l in word_hash if word_hash[l] > rack_hash[l]])

    def letters(self):
        return ''.join([l.letter for l in self._tiles])

    def next_letter(self):
        c = Counter(''.join([l.letter for l in self._tiles]))
        for k in c.keys():
            c[k] *= int(BAG_SIZE / MAX_LETTERS)
        frequencies = Counter(FREQUENCIES) # make a copy
        frequencies.subtract(c)

        bag = [letter for letter, frequency in frequencies.items() for _ in range(frequency)]
        return random.choice(bag)

    def replace_letter(self, new_letter, position):
        logging.info(f"\nreplace_letter() {new_letter} -> {str(self)}, new_letter: {new_letter}")
        remove_tile = self._tiles[position]

        remove_tile.letter = new_letter
        logging.info(f"final: {str(self)}")
        return self
