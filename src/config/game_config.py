"""Centralized configuration for the BlockWords game, including display, game logic, and MQTT settings."""

import os
from pygame import Color

# ============================================================================
# DISPLAY SETTINGS
# ============================================================================
SCREEN_WIDTH = 192
SCREEN_HEIGHT = 256
SCALING_FACTOR = 3
TICKS_PER_SECOND = 45

# Font settings
FONT = "Courier"
ANTIALIAS = 1
FONT_SIZE_DELTA = 4

# Colors - Guess feedback
BAD_GUESS_COLOR = Color("red")
GOOD_GUESS_COLOR = Color("Green")
OLD_GUESS_COLOR = Color("yellow")
LETTER_SOURCE_COLOR = Color("Red")

# Colors - Game elements
RACK_COLOR = Color("LightGrey")
SHIELD_COLOR_P0 = Color("DarkOrange4")
SHIELD_COLOR_P1 = Color("DarkSlateBlue")
SCORE_COLOR = Color("White")
FADER_COLOR_P0 = Color("orange")
FADER_COLOR_P1 = Color("lightblue")
REMAINING_PREVIOUS_GUESSES_COLOR = Color("grey")
PREVIOUS_GUESSES_COLOR = Color("orange")

# Player color arrays
PLAYER_COLORS = [SHIELD_COLOR_P0, SHIELD_COLOR_P1]
FADER_PLAYER_COLORS = [FADER_COLOR_P0, FADER_COLOR_P1]


# ============================================================================
# GAME LOGIC SETTINGS
# ============================================================================
MAX_PLAYERS = 2
MIN_LETTERS = 3  # Minimum word length
MAX_LETTERS = 6  # Maximum word length
FREE_SCORE = 0

# Timing settings
ABC_COUNTDOWN_DELAY_MS = 1000  # Delay for ABC countdown sequence (ms)
UPDATE_TILES_REBROADCAST_S = 8  # How often to rebroadcast tile updates (seconds)
TIMED_DURATION_S = 10  # Default duration for timed mode games (seconds)

# Scrabble letter scores for word scoring
SCRABBLE_LETTER_SCORES = {
    'A': 1, 'B': 3, 'C': 3, 'D': 2, 'E': 1, 'F': 4,
    'G': 2, 'H': 4, 'I': 1, 'J': 8, 'K': 5, 'L': 1,
    'M': 3, 'N': 1, 'O': 1, 'P': 3, 'Q': 10, 'R': 1,
    'S': 1, 'T': 1, 'U': 1, 'V': 4, 'W': 4, 'X': 8,
    'Y': 4, 'Z': 10
}


# ============================================================================
# MQTT SETTINGS
# ============================================================================
MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")
MQTT_CLIENT_ID = 'game-server'
MQTT_CLIENT_PORT = 1883
# ============================================================================
# PATH SETTINGS
# ============================================================================
DATA_DIR = "assets/data"
DICTIONARY_PATH = os.path.join(DATA_DIR, "sowpods.txt")
BINGOS_PATH = os.path.join(DATA_DIR, "bingos.txt")
