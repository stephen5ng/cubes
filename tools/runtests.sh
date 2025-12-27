#!/bin/bash
export PYTHONPATH=../easing-functions
python -X dev -X tracemalloc=5 -m unittest test_app.py test_cubes_to_game.py test_dictionary.py test_scorecard.py test_tiles.py
mypy *.py
