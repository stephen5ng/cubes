from bottle import request, route, run, static_file, template
from collections import Counter
import random

my_open = open

MAX_LETTERS = 7
dictionary = None
previous_guesses = set()
score = 0
tiles = None

SCRABBLE_LETTER_FREQUENCIES = {
    'A': 9, 'B': 2, 'C': 2, 'D': 4, 'E': 12, 'F': 2, 'G': 3, 'H': 2, 'I': 9, 'J': 1, 'K': 1, 'L': 4, 'M': 2,
    'N': 6, 'O': 8, 'P': 2, 'Q': 1, 'R': 6, 'S': 4, 'T': 6, 'U': 4, 'V': 2, 'W': 2, 'X': 1, 'Y': 2, 'Z': 1
}
SCRABBLE_LETTERS = [letter for letter, frequency in SCRABBLE_LETTER_FREQUENCIES.items() for _ in range(frequency)]

SCRABBLE_LETTER_SCORES = {
    'A': 1, 'B': 3, 'C': 3, 'D': 2, 'E': 1, 'F': 4, 'G': 2, 'H': 4, 'I': 1, 'J': 8, 'K': 5, 'L': 1, 'M': 3,
    'N': 1, 'O': 1, 'P': 3, 'Q': 10, 'R': 1, 'S': 1, 'T': 1, 'U': 1, 'V': 4, 'W': 4, 'X': 8, 'Y': 4, 'Z': 10
}

class Tiles:
    def __init__(self, letters):
        self._letters = letters
        self._last_guess = ""
        self._unused_letters = letters

    def display(self):
        return f"{self._last_guess} {self._unused_letters}"

    def guess(self, guess):
        self._last_guess = guess
        self._unused_letters = remove_letters(self._letters, guess)

    def has_word(self, word):
        tiles_hash = Counter(self._letters)
        word_hash = Counter(word)
        return all(word_hash[letter] <= tiles_hash[letter] for letter in word)

    def letters(self):
        return self._letters

    def replace_letter(self, new_letter):
        if self._unused_letters:
            remove_ix = random.randint(0, len(self._unused_letters)-1)
            self._unused_letters = "".join(sorted(self._unused_letters[:remove_ix] + 
                self._unused_letters[remove_ix+1:] + new_letter))
        else:
            remove_ix = random.randint(0, len(self._last_guess)-1)
            self._last_guess = (self._last_guess[:remove_ix] + 
                self._last_guess[remove_ix+1:])
            self._unused_letters = new_letter
        self._letters = self._last_guess + self._unused_letters


class Dictionary:
    def __init__(self, open=open):
        self._open = open
        self._words = []
        self._word_frequencies = {}

    def read(self, filename):
        with self._open(filename, "r") as f:
            for line in f:
                line = line.strip()
                count, word = line.split(" ")
                word = word.upper()
                self._word_frequencies[word] = int(count)
                if len(word) != MAX_LETTERS:
                    continue
                self._words.append(word)

    def get_tiles(self):
        return Tiles(sort_word(random.choice(self._words)))

    def is_word(self, word):
        return word in self._word_frequencies

def remove_letters(source_string, letters_to_remove):
    for char in letters_to_remove:
        source_string = source_string.replace(char, '', 1)
    return source_string

def sort_word(word):
    return "".join(sorted(word))

@route('/')
def index():
    global previous_guesses, score, tiles
    previous_guesses = set()
    tiles = dictionary.get_tiles()
    score = 0
    return template('index', tiles=tiles.letters(), next_tile=next_tile())

@route('/get_rack')
def get_rack():
    tiles.replace_letter(request.query.get('next_letter'))
    return tiles.display()

def calculate_score(word):
    return sum(SCRABBLE_LETTER_SCORES.get(letter, 0) for letter in word)

@route('/get_previous_guesses')
def get_previous_guesses():
    return " ".join(sorted(list(previous_guesses)))

@route('/get_score')
def get_score():
    return str(score)

@route('/guess_word')
def guess_word():
    global score, tiles
    guess = request.query.get('guess').upper()
    response = {}
    if guess in previous_guesses:
        return { 'status': f"already played {guess}",
                 'current_score': 0
                }

    if not dictionary.is_word(guess):
        return { 'status': f"{guess} is not a word",
                 'current_score': 0
               }

    if not tiles.has_word(guess):
        return { 'status': f"can't make {guess} from {tiles.letters()}",
                 'current_score': 0
                }

    tiles.guess(guess)
    previous_guesses.add(guess)
    current_score = calculate_score(guess)
    score += current_score
    return {
            'status': f"guess: {guess}",
            'current_score': current_score,
            'score': score,
            'tiles': f"{tiles.display()}"}

@route('/next_tile')
def next_tile():
    # TODO: Don't create a rack that has no possible words.
    next_tile = random.choice(SCRABBLE_LETTERS)
    return next_tile

@route('/static/<filename>')
def server_static(filename):
    return static_file(filename, root='.')

def init():
    global dictionary
    dictionary = Dictionary(open = my_open)
    dictionary.read("../sowpods.count.withzeros.sevenless.txt")

if __name__ == '__main__':
    init()
    run(host='localhost', port=8080)
