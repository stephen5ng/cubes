#!/bin/bash -ex
. cube_env/bin/activate

trap "kill 0" EXIT

duration="${1:-0.1}"


python fake_tile_sequences.py --duration $duration --player 2 &

./runpygame.sh
