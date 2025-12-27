"""Display constants for the BlockWords game."""

import pygame
from pygame import Color

# Screen dimensions
SCREEN_WIDTH = 192
SCREEN_HEIGHT = 256
SCALING_FACTOR = 3

# Game timing
TICKS_PER_SECOND = 45

# Font settings
FONT = "Courier"
ANTIALIAS = 1
FONT_SIZE_DELTA = 4

# Score settings
FREE_SCORE = 0

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
