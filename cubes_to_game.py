#!/usr/bin/env python3

import aiomqtt
import asyncio
import json
import logging
import os
import re
import requests
import sys
import time
from typing import Callable, Coroutine, Dict, List, Optional

import tiles
# "Tags" are nfc ids
# "Cubes" are the MAC address of the ESP32
# "Tiles" are the tile number assigned by the app (usually 0-6)

TAGS_TO_CUBES : Dict[str, str] = {}

# Linked list of cubes which are adjacent to each other, left-to-right
cube_chain : Dict[str, str] = {}

cubes_to_letters : Dict[str, str] = {}
tiles_to_cubes : Dict[str, str] = {}
cubes_to_tileid : Dict[str, str] = {}
cubes_to_neighbortags : Dict[str, str] = {}
# logging.basicConfig(stream=sys.stdout, level=logging.INFO)

def find_unmatched_cubes():
    sources = set(cube_chain.keys())
    targets = set(cube_chain.values())
    return list(sources - targets)

def remove_back_pointer(target_cube: str):
    for source in cube_chain:
        if cube_chain[source] == target_cube:
            # print(f"removing {source}: {cubes_to_letters[source]}")
            del cube_chain[source]
            break

def print_cube_chain():
    if not cubes_to_letters:
        return
    try:
        s = ""
        for source in cube_chain:
            target = cube_chain[source]
            s += f"{source} [{cubes_to_letters[source]}] -> {target} [{cubes_to_letters[target]}]; "
        return s
    except Exception as e:
        logging.error(f"print_cube_chain ERROR: {e}")

def dump_cubes_to_neighbortags():
    for cube in TAGS_TO_CUBES.values():
        log_str = f"{cube} [{cubes_to_letters.get(cube, '')}]"
        if cube in cubes_to_neighbortags:
            neighbor = cubes_to_neighbortags[cube]
            neighbor_cube = TAGS_TO_CUBES.get(neighbor, "")
            log_str += f"-> {neighbor},{neighbor_cube}"
            log_str += f"[{cubes_to_letters.get(neighbor_cube, '')}]"
        logging.info(log_str)
    logging.info("")

def process_tag(sender_cube: str, tag: str) -> List[str]:
    # Returns lists of tileids
    cubes_to_neighbortags[sender_cube] = tag
    dump_cubes_to_neighbortags()
    logging.info(f"process_tag {sender_cube}: {tag}")
    logging.info(f"process_tag0 cube_chain {cube_chain}")
    if not tag:
        logging.info(f"process_tag: no tag, deleting target of {sender_cube}")
        if sender_cube in cube_chain:
            del cube_chain[sender_cube]
    elif tag not in TAGS_TO_CUBES:
        logging.info(f"bad tag: {tag}")
        if sender_cube in cube_chain:
            del cube_chain[sender_cube]
    else:
        target_cube = TAGS_TO_CUBES[tag]
        if sender_cube == target_cube:
            # print(f"cube can't point to itself")
            return []

        logging.info(f"process_tag: {sender_cube} -> {target_cube}")
        if target_cube in cube_chain.values():
            # sender overrides existing chain--must have missed a remove message, process it now.
            logging.info(f"override: remove back pointer for {target_cube}")
            # might cause trouble because ordering of QOS 1 is not guaranteed
            # https://stackoverflow.com/questions/30955110/is-message-order-preserved-in-mqtt-messages
            # ignore the dupe and hope it works out
            # remove_back_pointer(target_cube)
        cube_chain[sender_cube] = TAGS_TO_CUBES[tag]

    logging.info(f"process_tag1 cube_chain {cube_chain}")

    # search for and remove any new loops
    source_cube = sender_cube
    iter_length = 0
    while source_cube:
        iter_length += 1
        if iter_length > tiles.MAX_LETTERS:
            logging.info(f"forever loop, bailing")
            return []
            raise Exception("")
        if not source_cube in cube_chain:
            break
        next_cube = cube_chain[source_cube]
        if next_cube == sender_cube:
            logging.info(f"breaking chain {print_cube_chain()}")
            return []
            del cube_chain[source_cube]
            logging.info(f"breaking chain done {print_cube_chain()}")
            break
        source_cube = next_cube
    logging.info(f"process_tag2 cube_chain {cube_chain}")

    logging.info(f"process_tag final cube_chain: {print_cube_chain()}")
    if not cube_chain:
        # No links at all, quit.
        return []

    all_words = []
    source_cubes = find_unmatched_cubes()
    for source_cube in sorted(source_cubes):
        word_tiles = []
        sc = source_cube
        while sc:
            logging.info(f"source_cube: {source_cube}")
            word_tiles.append(cubes_to_tileid[sc])
            if len(word_tiles) > tiles.MAX_LETTERS:
                logging.info("infinite loop")
                return []
                # raise Exception("infinite loop")
            if sc not in cube_chain:
                break
            sc = cube_chain[sc]
        all_words.append("".join(word_tiles))
    logging.info(f"all_words is {all_words}")
    all_elements = [item for lst in all_words for item in lst]
    if len(all_elements) != len(set(all_elements)):
        logging.info(f"DUPES: {all_words}")
        return []

    logging.info(f"all_words {all_words}")
    return all_words

def initialize_arrays():
    tiles_to_cubes.clear()
    cubes_to_tileid.clear()

    cubes = list(TAGS_TO_CUBES.values())
    for ix in range(tiles.MAX_LETTERS+1):
        if ix >= len(cubes):
            break
        tile_id = str(ix)
        tiles_to_cubes[tile_id] = cubes[ix]
        cubes_to_tileid[cubes[ix]] = tile_id

async def load_rack_only(publish_queue, tiles_with_letters: list[tiles.Tile]):
    logging.info(f"LOAD RACK tiles_with_letters: {tiles_with_letters}")
    for tile in tiles_with_letters:
        tile_id = tile.id
        cube_id = tiles_to_cubes[tile_id]
        letter = tile.letter
        cubes_to_letters[cube_id] = letter
        await publish_letter(publish_queue, letter, cube_id)
    logging.info(f"LOAD RACK tiles_with_letters done: {cubes_to_letters}")

async def accept_new_letter(publish_queue, letter, tile_id):
    cube_id = tiles_to_cubes[tile_id]
    cubes_to_letters[cube_id] = letter
    await publish_letter(publish_queue, letter, cube_id)

async def publish_letter(publish_queue, letter, cube_id):
    await publish_queue.put((f"cube/{cube_id}/letter", letter, True))

last_tiles_with_letters : list[tiles.Tile] = []
async def load_rack(publish_queue, tiles_with_letters: list[tiles.Tile]):
    global last_tiles_with_letters
    await load_rack_only(publish_queue, tiles_with_letters)

    if last_tiles_with_letters != tiles_with_letters:
        # Some of the tiles changed. Make a guess, just in case one of them
        # was in our last guess (which is overkill).
        logging.info(f"LOAD RACK guessing")
        await guess_last_tiles(publish_queue)
        last_tiles_with_letters = tiles_with_letters

async def guess_tiles(publish_queue, word_tiles_list):
    global last_guess_tiles
    last_guess_tiles = word_tiles_list
    await guess_last_tiles(publish_queue)

last_guess_time_s = time.time()
last_guess_tiles: List[str] = []
DEBOUNCE_TIME_S = 10
async def guess_word_based_on_cubes(sender: str, tag: str, publish_queue):
    global last_guess_time_s, last_guess_tiles
    now_s = time.time()
    word_tiles_list = process_tag(sender, tag)
    logging.info(f"WORD_TILES: {word_tiles_list}")
    if word_tiles_list == last_guess_tiles and now_s - last_guess_time_s < DEBOUNCE_TIME_S:
        logging.info(f"debounce ignoring guess")
        last_guess_time_s = now_s
        return
    last_guess_time_s = now_s
    await guess_tiles(publish_queue, word_tiles_list)

guess_tiles_callback: Callable[[str, bool], Coroutine[None, None, None]]

def set_guess_tiles_callback(f):
    global guess_tiles_callback
    guess_tiles_callback = f

def get_cubeids_from_tiles(word_tiles):
    return [tiles_to_cubes[t] for t in word_tiles]

async def guess_last_tiles(publish_queue) -> None:
    unused_tiles = set((str(i) for i in range(tiles.MAX_LETTERS)))
    logging.info(f"guess_last_tiles last_guess_tiles {last_guess_tiles} {unused_tiles}")
    for guess in last_guess_tiles:
        logging.info(f"guess_last_tiles: {guess}")
        # Skip single-tile guesses
        if len(guess) <= 1:
            continue
            
        for i, tile in enumerate(guess):
            unused_tiles.remove(tile)
            marker = '[' if i == 0 else ']' if i == len(guess)-1 else '-'
            await publish_queue.put((f"cube/{tiles_to_cubes[tile]}/border_line", marker, True))

    for g in unused_tiles:
        await publish_queue.put((f"cube/{tiles_to_cubes[g]}/border_line", ' ', True))

    for guess in last_guess_tiles:
        await guess_tiles_callback(guess, True)

async def good_guess(publish_queue, tiles: list[str]):
    for t in tiles:
        await publish_queue.put((f"cube/{tiles_to_cubes[t]}/flash", None, True))
        await publish_queue.put((f"cube/{tiles_to_cubes[t]}/border_color", "G", True))

async def old_guess(publish_queue, tiles: list[str]):
    for t in tiles:
        await publish_queue.put((f"cube/{tiles_to_cubes[t]}/border_color", "Y", True))

async def bad_guess(publish_queue, tiles: list[str]):
    for t in tiles:
        await publish_queue.put((f"cube/{tiles_to_cubes[t]}/border_color", "W", True))

async def process_cube_guess(publish_queue, topic: aiomqtt.Topic, data: str):
    logging.info(f"process_cube_guess: {topic} {data}")
    sender = topic.value.removeprefix("cube/nfc/")
    await publish_queue.put((f"game/nfc/{sender}", data, True))
    await guess_word_based_on_cubes(sender, data, publish_queue)

def read_data(f):
    data = f.readlines()
    data = [l.strip() for l in data]
    return data

def get_tags_to_cubes(cubes_file: str, tags_file: str):
    with open(cubes_file) as cubes_f:
        with open(tags_file) as tags_f:
            return get_tags_to_cubes_f(cubes_f, tags_f)

def get_tags_to_cubes_f(cubes_f, tags_f):
    cubes = read_data(cubes_f)
    tags = read_data(tags_f)

    tags_to_cubes = {}
    for cube, tag in zip(cubes, tags):
        tags_to_cubes[tag] = cube
    return tags_to_cubes

async def init(subscribe_client, cubes_file, tags_file):
    global TAGS_TO_CUBES
    logging.info("cubes_to_game")
    TAGS_TO_CUBES = get_tags_to_cubes(cubes_file, tags_file)
    logging.info(f"ttc: {TAGS_TO_CUBES}")

    initialize_arrays()
    await subscribe_client.subscribe("cube/nfc/#")

async def handle_mqtt_message(publish_queue, message):
    await process_cube_guess(publish_queue, message.topic, message.payload.decode())
