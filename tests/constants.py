"""Shared test constants.

This module contains constants used across multiple integration tests to avoid
duplication and ensure consistency.
"""

# Frame timing constants
FRAME_DURATION_MS = 16  # ~16ms per frame at 60 FPS
MAX_SIMULATION_FRAMES = 600  # Maximum frames for run_until_condition

# ABC countdown constants
ABC_COUNTDOWN_FRAMES = 50  # Frames needed for countdown completion and event propagation

# Shield test constants
SHIELD_X = 100
SHIELD_Y = 400
SHIELD_HEALTH = 100
BOUNCE_DETECTION_THRESHOLD = 50
SHIELD_APPROACH_DISTANCE = 20
SHIELD_PENETRATION_TOLERANCE = 50
