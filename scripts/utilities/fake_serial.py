#!/usr/bin/env python3

# Emit output that look like updates from the cubes.

import argparse
import logging
import random
import sys
import time

def read_data(filename):
    with open(filename) as f:
        data = f.readlines()
    data = [l.strip() for l in data]
    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sleep", type=float)
    parser.add_argument("--tags", type=str)
    parser.add_argument("--cubes", type=str)
    parser.add_argument("--random", default=False, type=bool)
    args = parser.parse_args()

    random.seed(0)
    tag_ids = read_data(args.tags)
    cube_ids = read_data(args.cubes)
    tag_ids.append("")
    tag_ix = cube_ix = -1
    while True:
        if args.random:
            tag_ix = random.randrange(0, len(tag_ids))
            cube_ix = random.randrange(0, len(cube_ids))
        else:
            tag_ix = (tag_ix + 1) % len(tag_ids)
            cube_ix = (cube_ix + 1) % len(cube_ids)

        print(f"{cube_ids[cube_ix]}:{tag_ids[tag_ix]}")
        time.sleep(args.sleep)
