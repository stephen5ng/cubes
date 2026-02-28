#!/bin/bash
# Wrapper script to run the game with mini display
# Usage: ./run_game_mini.sh [args]
# Example: ./run_game_mini.sh --mode game_on

exec sudo LED_DISPLAY_TYPE=mini /home/dietpi/lexacube-dev/cube_env/bin/python3 /home/dietpi/lexacube-dev/runpygame.py "$@"
