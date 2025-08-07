#!/usr/bin/env python3

import asyncio
from io import StringIO
import random
import unittest
from unittest import IsolatedAsyncioTestCase

import app
import dictionary
from pygameasync import events
import cubes_to_game
import tiles

class TestCubesToGame(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        async def nop(*a):
            pass

        self.publish_queue: asyncio.Queue = asyncio.Queue()
        my_open = lambda filename, mode: StringIO("\n".join([
            "arch",
            "fuzz",
            "line",
            "search",
            "online" # eilnno
        ])) if filename == "sowpods.txt" else StringIO("\n".join([
            "search", # ACEHRS
            "online"
        ]))
        random.seed(1)
        events.on("game.bad_guess")(nop)
        events.on("game.next_tile")(nop)
        events.on("game.stage_guess")(nop)
        events.on("rack.update_letter")(nop)
        events.on("rack.update_rack")(nop)
        events.on("input.remaining_previous_guesses")(nop)
        events.on("input.update_previous_guesses")(nop)
        events.on("game.current_score")(nop)
        self.client = Client([])

        a_dictionary = dictionary.Dictionary(3, 6, my_open)
        a_dictionary.read("sowpods.txt", "bingos.txt")
        self.the_app = app.App(self.publish_queue, a_dictionary)

        # Create a cube manager instance
        self.cube_manager = cubes_to_game.CubeManager(0)
        self.cube_manager.cubes_to_tileid["BLOCK_0"] = "0"
        self.cube_manager.cubes_to_tileid["BLOCK_1"] = "1"
        self.cube_manager.cubes_to_tileid["BLOCK_2"] = "2"
        self.cube_manager.cubes_to_tileid["BLOCK_3"] = "3"
        self.cube_manager.tags_to_cubes = {
            "TAG_0": "BLOCK_0",
            "TAG_1": "BLOCK_1",
            "TAG_2": "BLOCK_2",
            "TAG_3": "BLOCK_3",
            "TAG_4": "BLOCK_4",
            "TAG_5": "BLOCK_5"
        }
        self.cube_manager.cube_chain = {}

    def test_two_chain(self):
        self.assertEqual(["01"], self.cube_manager.process_tag("BLOCK_0", "TAG_1"))

    def test_multiple_chains(self):
        self.cube_manager.cube_chain["BLOCK_0"] = "BLOCK_1"
        self.assertEqual(['01', '23'], self.cube_manager.process_tag("BLOCK_2", "TAG_3"))

    def test_existing_chain(self):
        self.cube_manager.cube_chain["BLOCK_0"] = "BLOCK_1"
        self.assertEqual(["012"], self.cube_manager.process_tag("BLOCK_1", "TAG_2"))

    def test_break_2_chain(self):
        self.cube_manager.cube_chain["BLOCK_0"] = "BLOCK_1"
        self.assertEqual([], self.cube_manager.process_tag("BLOCK_1", "TAG_0"))

    def test_break_3_chain(self):
        self.cube_manager.cube_chain["BLOCK_0"] = "BLOCK_1"
        self.cube_manager.cube_chain["BLOCK_1"] = "BLOCK_2"
        self.assertEqual([], self.cube_manager.process_tag("BLOCK_2", "TAG_0"))

    def test_delete_link(self):
        self.cube_manager.cube_chain["BLOCK_0"] = "BLOCK_1"
        self.cube_manager.cube_chain["BLOCK_1"] = "BLOCK_2"
        self.assertEqual(["12"], self.cube_manager.process_tag("BLOCK_0", ""))

    def test_delete_link_nothing_left(self):
        self.assertEqual([], self.cube_manager.process_tag("BLOCK_0", ""))

    def test_bad_tag(self):
        self.assertEqual([], self.cube_manager.process_tag("BLOCK_0", "TAG_Z"))

    def test_sender_is_target(self):
        self.assertEqual([], self.cube_manager.process_tag("BLOCK_0", "TAG_0"))

class Message:
    def __init__(self, topic):
        self.topic = topic

class Client:
    def __init__(self, messages):
        self.messages = messages

    async def _messages_iter(self, messages):
        for message in messages:
            yield message

    async def publish(self, topic, *payload):
        pass
