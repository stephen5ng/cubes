# Global configuration values

# Game settings
MAX_PLAYERS = 2
MIN_LETTERS = 3  # Minimum word length
MAX_LETTERS = 6  # Maximum word length

# MQTT settings
MQTT_CLIENT_ID = 'game-server'
MQTT_CLIENT_PORT = 1883

# Timing settings (in milliseconds or seconds as noted)
ABC_COUNTDOWN_DELAY_MS = 1000  # Delay for ABC countdown sequence (ms)
UPDATE_TILES_REBROADCAST_S = 8  # How often to rebroadcast tile updates (seconds)

# Scrabble letter scores for word scoring
SCRABBLE_LETTER_SCORES = {
    'A': 1, 'B': 3, 'C': 3, 'D': 2, 'E': 1, 'F': 4,
    'G': 2, 'H': 4, 'I': 1, 'J': 8, 'K': 5, 'L': 1,
    'M': 3, 'N': 1, 'O': 1, 'P': 3, 'Q': 10, 'R': 1,
    'S': 1, 'T': 1, 'U': 1, 'V': 4, 'W': 4, 'X': 8,
    'Y': 4, 'Z': 10
} 