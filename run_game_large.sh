#!/bin/bash
# Wrapper script to run the game with large display
# Usage: ./run_game_large.sh [args]
# Example: ./run_game_large.sh --mode game_on

exec sudo LED_DISPLAY_TYPE=large /home/dietpi/lexacube-dev/cube_env/bin/python3 /home/dietpi/lexacube-dev/runpygame.py "$@"
