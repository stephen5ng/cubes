#!/bin/bash
export PYTHONPATH=../easing-functions
python -X dev -X tracemalloc=5 -m unittest app_test.py cubes_to_game_test.py dictionary_test.py scorecard_test.py tiles_test.py
mypy *.py
