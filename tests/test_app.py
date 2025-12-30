#!/usr/bin/env python3

import asyncio
from io import StringIO
import random
import unittest
from unittest import IsolatedAsyncioTestCase

from core import app
from core import dictionary
from utils.pygameasync import events
from hardware import cubes_to_game
from core import tiles

class TestCubeGame(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
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
        a_dictionary = dictionary.Dictionary(3, 6, my_open)
        a_dictionary.read("sowpods.txt", "bingos.txt")
        self.app = app.App(self.publish_queue, a_dictionary)
        # Don't start the app in tests to avoid initialization issues

    def test_sort(self) -> None:
        self.assertEqual("abc", dictionary._sort_word("cab"))

if __name__ == '__main__':
    unittest.main()
