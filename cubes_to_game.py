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

class CubeManager:
    def __init__(self):
        self.tags_to_cubes: Dict[str, str] = {}
        self.cube_chain: Dict[str, str] = {}
        self.cubes_to_letters: Dict[str, str] = {}
        self.tiles_to_cubes: Dict[str, str] = {}
        self.cubes_to_tileid: Dict[str, str] = {}
        self.cubes_to_neighbortags: Dict[str, str] = {}
        self.cubes_player_number: int = 0

    def _find_unmatched_cubes(self):
        sources = set(self.cube_chain.keys())
        targets = set(self.cube_chain.values())
        return list(sources - targets)

    def _print_cube_chain(self):
        if not self.cubes_to_letters:
            return
        try:
            s = ""
            for source in self.cube_chain:
                target = self.cube_chain[source]
                s += f"{source} [{self.cubes_to_letters[source]}] -> {target} [{self.cubes_to_letters[target]}]; "
            return s
        except Exception as e:
            logging.error(f"print_cube_chain ERROR: {e}")

    def _dump_cubes_to_neighbortags(self):
        for cube in self.tags_to_cubes.values():
            log_str = f"{cube} [{self.cubes_to_letters.get(cube, '')}]"
            if cube in self.cubes_to_neighbortags:
                neighbor = self.cubes_to_neighbortags[cube]
                neighbor_cube = self.tags_to_cubes.get(neighbor, "")
                log_str += f"-> {neighbor},{neighbor_cube}"
                log_str += f"[{self.cubes_to_letters.get(neighbor_cube, '')}]"
            logging.info(log_str)
        logging.info("")

    def _form_words_from_chain(self) -> List[str]:
        """Forms words from the current cube chain. Returns empty list if invalid."""
        if not self.cube_chain:
            return []

        all_words = []
        source_cubes = self._find_unmatched_cubes()
        for source_cube in sorted(source_cubes):
            word_tiles = []
            sc = source_cube
            while sc:
                if sc not in self.cubes_to_tileid:
                    return []
                word_tiles.append(self.cubes_to_tileid[sc])
                if len(word_tiles) > tiles.MAX_LETTERS:
                    logging.info("infinite loop")
                    return []
                if sc not in self.cube_chain:
                    break
                sc = self.cube_chain[sc]
            all_words.append("".join(word_tiles))

        # Check for duplicates
        all_elements = [item for lst in all_words for item in lst]
        if len(all_elements) != len(set(all_elements)):
            logging.info(f"DUPES: {all_words}")
            return []

        return all_words

    def _has_loop_from_cube(self, start_cube: str) -> bool:
        """Checks if adding a link from start_cube would create a loop.
        Returns True if a loop is detected, False otherwise."""
        source_cube = start_cube
        iter_length = 0
        while source_cube:
            iter_length += 1
            if iter_length > tiles.MAX_LETTERS:
                logging.info(f"forever loop, bailing")
                return True
            if not source_cube in self.cube_chain:
                break
            next_cube = self.cube_chain[source_cube]
            if next_cube == start_cube:
                logging.info(f"breaking chain {self._print_cube_chain()}")
                return True
            source_cube = next_cube
        return False

    def _update_chain(self, sender_cube: str, target_cube: str) -> bool:
        """Updates the chain with a new connection. Returns True if chain is valid."""
        if sender_cube == target_cube:
            return False
            
        self.cube_chain[sender_cube] = target_cube
        if self._has_loop_from_cube(sender_cube):
            del self.cube_chain[sender_cube]
            return False
        return True

    def process_tag(self, sender_cube: str, tag: str) -> List[str]:
        # Update neighbor tracking
        self.cubes_to_neighbortags[sender_cube] = tag
        self._dump_cubes_to_neighbortags()
        logging.info(f"process_tag {sender_cube}: {tag}")
        logging.info(f"process_tag cube_chain {self.cube_chain}")

        # Handle empty tag case
        if not tag:
            logging.info(f"process_tag: no tag, deleting target of {sender_cube}")
            if sender_cube in self.cube_chain:
                del self.cube_chain[sender_cube]
            return self._form_words_from_chain()

        # Validate tag and cube
        if tag not in self.tags_to_cubes:
            logging.info(f"bad tag: {tag}")
            if sender_cube in self.cube_chain:
                del self.cube_chain[sender_cube]
            return self._form_words_from_chain()

        target_cube = self.tags_to_cubes[tag]
        
        # Update chain if valid
        if not self._update_chain(sender_cube, target_cube):
            return []

        logging.info(f"process_tag final cube_chain: {self._print_cube_chain()}")
        return self._form_words_from_chain()

    def _initialize_arrays(self):
        self.tiles_to_cubes.clear()
        self.cubes_to_tileid.clear()

        cubes = list(self.tags_to_cubes.values())
        for ix in range(tiles.MAX_LETTERS+1):
            if ix >= len(cubes):
                break
            tile_id = str(ix)
            self.tiles_to_cubes[tile_id] = cubes[ix]
            self.cubes_to_tileid[cubes[ix]] = tile_id

    def get_tags_to_cubes(self, cubes_file: str, tags_file: str):
        with open(cubes_file) as cubes_f:
            with open(tags_file) as tags_f:
                return self.get_tags_to_cubes_f(cubes_f, tags_f)

    def get_tags_to_cubes_f(self, cubes_f, tags_f):
        cubes = read_data(cubes_f)
        tags = read_data(tags_f)
        return {tag: cube for cube, tag in zip(cubes, tags)}

    async def init(self, subscribe_client, cubes_file, tags_file, cubes_player_number_arg: int):
        self.cubes_player_number = cubes_player_number_arg
        logging.info("cubes_to_game")
        self.tags_to_cubes = self.get_tags_to_cubes(cubes_file, tags_file)
        logging.info(f"ttc: {self.tags_to_cubes}")

        self._initialize_arrays()
        await subscribe_client.subscribe("cube/nfc/#")

cube_manager = CubeManager()

async def _publish_letter(publish_queue, letter, cube_id):
    await publish_queue.put((f"cube/{cube_id}/letter", letter, True))

async def _load_rack_only(publish_queue, tiles_with_letters: list[tiles.Tile]):
    logging.info(f"LOAD RACK tiles_with_letters: {tiles_with_letters}")
    for tile in tiles_with_letters:
        tile_id = tile.id
        cube_id = cube_manager.tiles_to_cubes[tile_id]
        letter = tile.letter
        cube_manager.cubes_to_letters[cube_id] = letter
        await _publish_letter(publish_queue, letter, cube_id)
    logging.info(f"LOAD RACK tiles_with_letters done: {cube_manager.cubes_to_letters}")

async def accept_new_letter(publish_queue, letter, tile_id):
    cube_id = cube_manager.tiles_to_cubes[tile_id]
    cube_manager.cubes_to_letters[cube_id] = letter
    await publish_letter(publish_queue, letter, cube_id)

async def publish_letter(publish_queue, letter, cube_id):
    await publish_queue.put((f"cube/{cube_id}/letter", letter, True))

last_tiles_with_letters : list[tiles.Tile] = []
async def load_rack(publish_queue, tiles_with_letters: list[tiles.Tile]):
    global last_tiles_with_letters
    await _load_rack_only(publish_queue, tiles_with_letters)

    if last_tiles_with_letters != tiles_with_letters:
        # Some of the tiles changed. Make a guess, just in case one of them
        # was in our last guess (which is overkill).
        logging.info(f"LOAD RACK guessing")
        # TODO(sng): needs to check both rack sets.
        await guess_last_tiles(publish_queue, 0)
        last_tiles_with_letters = tiles_with_letters

async def guess_tiles(publish_queue, word_tiles_list, player: int):
    global last_guess_tiles
    last_guess_tiles = word_tiles_list
    await guess_last_tiles(publish_queue, player)

last_guess_time_s = time.time()
last_guess_tiles: List[str] = []
DEBOUNCE_TIME_S = 10
async def guess_word_based_on_cubes(sender: str, tag: str, publish_queue):
    global last_guess_time_s, last_guess_tiles
    now_s = time.time()
    word_tiles_list = cube_manager.process_tag(sender, tag)
    logging.info(f"WORD_TILES: {word_tiles_list}")
    if word_tiles_list == last_guess_tiles and now_s - last_guess_time_s < DEBOUNCE_TIME_S:
        logging.info(f"debounce ignoring guess")
        last_guess_time_s = now_s
        return
    last_guess_time_s = now_s
    await guess_tiles(publish_queue, word_tiles_list, cube_manager.cubes_player_number)

guess_tiles_callback: Callable[[str, bool], Coroutine[None, None, None]]

def set_guess_tiles_callback(f):
    global guess_tiles_callback
    guess_tiles_callback = f

def get_cubeids_from_tiles(word_tiles):
    return [cube_manager.tiles_to_cubes[t] for t in word_tiles]

async def guess_last_tiles(publish_queue, player: int) -> None:
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
            await publish_queue.put((f"cube/{cube_manager.tiles_to_cubes[tile]}/border_line", marker, True))

    for g in unused_tiles:
        await publish_queue.put((f"cube/{cube_manager.tiles_to_cubes[g]}/border_line", ' ', True))

    for guess in last_guess_tiles:
        await guess_tiles_callback(guess, True, player)

async def mark_guess(publish_queue, tiles: list[str], color: str, flash: bool):
    for t in tiles:
        if flash:
            await publish_queue.put((f"cube/{cube_manager.tiles_to_cubes[t]}/flash", None, True))
        await publish_queue.put((f"cube/{cube_manager.tiles_to_cubes[t]}/border_color", color, True))

async def process_cube_guess(publish_queue, topic: aiomqtt.Topic, data: str):
    logging.info(f"process_cube_guess: {topic} {data}")
    sender = topic.value.removeprefix("cube/nfc/")
    await publish_queue.put((f"game/nfc/{sender}", data, True))
    await guess_word_based_on_cubes(sender, data, publish_queue)

def read_data(f):
    data = f.readlines()
    data = [l.strip() for l in data]
    return data

async def init(subscribe_client, cubes_file, tags_file, cubes_player_number_arg: int):
    await cube_manager.init(subscribe_client, cubes_file, tags_file, cubes_player_number_arg)

async def handle_mqtt_message(publish_queue, message):
    await process_cube_guess(publish_queue, message.topic, message.payload.decode())

async def good_guess(publish_queue, tiles: list[str]):
    await mark_guess(publish_queue, tiles, "G", True)

async def old_guess(publish_queue, tiles: list[str]):
    await mark_guess(publish_queue, tiles, "Y", False)

async def bad_guess(publish_queue, tiles: list[str]):
    await mark_guess(publish_queue, tiles, "W", False)
