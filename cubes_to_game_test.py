#!/usr/bin/env python3

import aiomqtt
import asyncio
import io
import json
from io import StringIO
import unittest
from unittest.mock import Mock, patch, AsyncMock

import app
import cubes_to_game
import dictionary
from pygameasync import events
import tiles

class FakeResponse:
    def __init__(self, value):
        self.__value = value

    def json(self):
        return self.__value


written = []
async def writer(s):
    global written
    written.append(s)

class TestCubesToGame(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        async def nop(*a):
            pass
        my_open = lambda filename, mode: StringIO("\n".join([
            "arch",
            "fuzz",
            "line",
            "search",
            "online" # eilnno
        ]))

        self.publish_queue: asyncio.Queue = asyncio.Queue()

        global written
        written = []
        rack = tiles.Rack("ABCD")
        cubes_to_game.cubes_to_tileid["BLOCK_0"] = str(rack._tiles[0].id)
        cubes_to_game.cubes_to_tileid["BLOCK_1"] = str(rack._tiles[1].id)
        cubes_to_game.cubes_to_tileid["BLOCK_2"] = str(rack._tiles[2].id)
        cubes_to_game.cubes_to_tileid["BLOCK_3"] = str(rack._tiles[3].id)
        cubes_to_game.TAGS_TO_CUBES = {
            "TAG_0": "BLOCK_0",
            "TAG_1": "BLOCK_1",
            "TAG_2": "BLOCK_2",
            "TAG_3": "BLOCK_3",
            "TAG_4": "BLOCK_4",
            "TAG_5": "BLOCK_5"
        }
        cubes_to_game.cube_chain = {}
        cubes_to_game.cubes_to_letters = {}
        cubes_to_game.last_guess_tiles = []
        events.on("game.current_score")(nop)
        self.client = Client([])

        a_dictionary = dictionary.Dictionary(3, 6, my_open)
        a_dictionary.read("sowpods.txt", "bingos.txt")
        self.the_app = app.App(self.publish_queue, a_dictionary)
        cubes_to_game.initialize_arrays()

    def test_two_chain(self):
        self.assertEqual(["01"], cubes_to_game.process_tag("BLOCK_0", "TAG_1"))

    def test_multiple_chains(self):
        cubes_to_game.cube_chain["BLOCK_0"] = "BLOCK_1"
        self.assertEqual(['01', '23'], cubes_to_game.process_tag("BLOCK_2", "TAG_3"))

    def test_existing_chain(self):
        cubes_to_game.cube_chain["BLOCK_0"] = "BLOCK_1"
        self.assertEqual(["012"], cubes_to_game.process_tag("BLOCK_1", "TAG_2"))

    def test_break_2_chain(self):
        cubes_to_game.cube_chain["BLOCK_0"] = "BLOCK_1"
        self.assertEqual([], cubes_to_game.process_tag("BLOCK_1", "TAG_0"))

    def test_break_3_chain(self):
        cubes_to_game.cube_chain["BLOCK_0"] = "BLOCK_1"
        cubes_to_game.cube_chain["BLOCK_1"] = "BLOCK_2"
        self.assertEqual([], cubes_to_game.process_tag("BLOCK_2", "TAG_0"))

    def test_delete_link(self):
        cubes_to_game.cube_chain["BLOCK_0"] = "BLOCK_1"
        cubes_to_game.cube_chain["BLOCK_1"] = "BLOCK_2"
        self.assertEqual(["12"], cubes_to_game.process_tag("BLOCK_0", ""))

    def test_delete_link_nothing_left(self):
        self.assertEqual([], cubes_to_game.process_tag("BLOCK_0", ""))

    def test_bad_tag(self):
        self.assertEqual([], cubes_to_game.process_tag("BLOCK_0", "TAG_Z"))

    def test_sender_is_target(self):
        self.assertEqual([], cubes_to_game.process_tag("BLOCK_0", "TAG_0"))

    def test_get_tags_to_cubes(self):
        cubes_file = io.StringIO("CUBE_0000000\nCUBE_0000001\nCUBE_0000002")
        tags_file = io.StringIO("TAG_0000000\nTAG_0000001\nTAG_0000002")
        result = cubes_to_game.get_tags_to_cubes_f(cubes_file, tags_file)
        expected = {
            'TAG_0000000': 'CUBE_0000000',
            'TAG_0000001': 'CUBE_0000001',
            'TAG_0000002': 'CUBE_0000002'}
        self.assertEqual(expected, result)

    async def test_process_cube_guess(self):
        await cubes_to_game.process_cube_guess(self.publish_queue,
            aiomqtt.Topic("cube/nfc/SENDER_ID"), "BLOCK_0:TAG_1")
        self.assertEqual([('game/nfc/SENDER_ID', 'BLOCK_0:TAG_1', True)],
            list(self.publish_queue._queue))

    async def test_load_rack(self):
        cubes_to_game.cubes_to_letters = {}
        self.the_app._player_rack = tiles.Rack("ABCDEF")
        cubes_to_game.initialize_arrays()
        cubes_to_game.last_guess_tiles = ['01']
        await cubes_to_game.load_rack(self.publish_queue,
            self.the_app._player_rack.get_tiles())
        self.assertEqual(
            [
             ('cube/BLOCK_0/border_line', '[', True),
             ('cube/BLOCK_0/letter', 'A', True),
             ('cube/BLOCK_1/border_line', ']', True),
             ('cube/BLOCK_1/letter', 'B', True),
             ('cube/BLOCK_2/border_line', ' ', True),
             ('cube/BLOCK_2/letter', 'C', True),
             ('cube/BLOCK_3/border_line', ' ', True),
             ('cube/BLOCK_3/letter', 'D', True),
             ('cube/BLOCK_4/border_line', ' ', True),
             ('cube/BLOCK_4/letter', 'E', True),
             ('cube/BLOCK_5/border_line', ' ', True),
             ('cube/BLOCK_5/letter', 'F', True)
             ],
            sorted(list(self.publish_queue._queue)))

    async def test_load_rack_only(self):
        cubes_to_game.cubes_to_letters = {}
        self.the_app._player_rack = tiles.Rack("ABCDEF")
        cubes_to_game.initialize_arrays()

        await cubes_to_game.load_rack_only(self.publish_queue,
            self.the_app._player_rack.get_tiles())

        self.assertEqual(
             {'BLOCK_0': 'A', 'BLOCK_1': 'B', 'BLOCK_2': 'C', 'BLOCK_3': 'D', 'BLOCK_4': 'E', 'BLOCK_5': 'F'},
            cubes_to_game.cubes_to_letters)
        self.assertEqual(
             {'0': 'BLOCK_0', '1': 'BLOCK_1', '2': 'BLOCK_2', '3': 'BLOCK_3', '4': 'BLOCK_4', '5': 'BLOCK_5'},
            cubes_to_game.tiles_to_cubes)
        self.assertEqual(
            [('cube/BLOCK_0/letter', 'A', True),
             ('cube/BLOCK_1/letter', 'B', True),
             ('cube/BLOCK_2/letter', 'C', True),
             ('cube/BLOCK_3/letter', 'D', True),
             ('cube/BLOCK_4/letter', 'E', True),
             ('cube/BLOCK_5/letter', 'F', True)],
            list(self.publish_queue._queue))

    async def test_guess_word_based_on_cubes(self):
        await cubes_to_game.guess_word_based_on_cubes("BLOCK_0", "TAG_1", self.publish_queue)
        expected = [
            ('cube/BLOCK_0/border_line', '[', True),
            ('cube/BLOCK_1/border_line', ']', True),
            ('cube/BLOCK_2/border_line', ' ', True),
            ('cube/BLOCK_3/border_line', ' ', True),
            ('cube/BLOCK_4/border_line', ' ', True),
            ('cube/BLOCK_5/border_line', ' ', True)]
        self.assertEqual(expected, sorted(list(self.publish_queue._queue)))

    async def test_guess_last_tiles_empty(self):
        """Test guess_last_tiles with empty last_guess_tiles."""
        # Mock the callback
        self.mock_callback = AsyncMock()
        cubes_to_game.guess_tiles_callback = self.mock_callback
        
        cubes_to_game.tiles_to_cubes = {
            "0": "cube_0",
            "1": "cube_1",
            "2": "cube_2",
            "3": "cube_3",
            "4": "cube_4",
            "5": "cube_5"
        }
        cubes_to_game.last_guess_tiles = []
        await cubes_to_game.guess_last_tiles(self.publish_queue)
        
        # All cubes should get space markers
        expected = [
            ('cube/cube_0/border_line', ' ', True),
            ('cube/cube_1/border_line', ' ', True),
            ('cube/cube_2/border_line', ' ', True),
            ('cube/cube_3/border_line', ' ', True),
            ('cube/cube_4/border_line', ' ', True),
            ('cube/cube_5/border_line', ' ', True)
        ]
        self.assertEqual(expected, sorted(list(self.publish_queue._queue)))
        self.assertEqual(0, self.mock_callback.call_count)

    async def test_guess_last_tiles_single_letter(self):
        """Test guess_last_tiles with a single-letter word."""
        # Mock the callback
        self.mock_callback = AsyncMock()
        cubes_to_game.guess_tiles_callback = self.mock_callback
        
        cubes_to_game.tiles_to_cubes = {
            "0": "cube_0",
            "1": "cube_1",
            "2": "cube_2",
            "3": "cube_3",
            "4": "cube_4",
            "5": "cube_5"
        }
        cubes_to_game.last_guess_tiles = ["0"]
        await cubes_to_game.guess_last_tiles(self.publish_queue)
        
        expected = [
            ('cube/cube_0/border_line', '[', True),  # Start marker
            ('cube/cube_0/border_line', ']', True),  # End marker (same cube)
            ('cube/cube_1/border_line', ' ', True),
            ('cube/cube_2/border_line', ' ', True),
            ('cube/cube_3/border_line', ' ', True),
            ('cube/cube_4/border_line', ' ', True),
            ('cube/cube_5/border_line', ' ', True)
        ]
        self.assertEqual(expected, sorted(list(self.publish_queue._queue)))
        self.mock_callback.assert_called_once_with("0", True)

    async def test_guess_last_tiles_two_letters(self):
        """Test guess_last_tiles with a two-letter word."""
        # Mock the callback
        self.mock_callback = AsyncMock()
        cubes_to_game.guess_tiles_callback = self.mock_callback
        
        cubes_to_game.tiles_to_cubes = {
            "0": "cube_0",
            "1": "cube_1",
            "2": "cube_2",
            "3": "cube_3",
            "4": "cube_4",
            "5": "cube_5"
        }
        cubes_to_game.last_guess_tiles = ["01"]
        await cubes_to_game.guess_last_tiles(self.publish_queue)
        
        expected = [
            ('cube/cube_0/border_line', '[', True),  # Start marker
            ('cube/cube_1/border_line', ']', True),  # End marker
            ('cube/cube_2/border_line', ' ', True),
            ('cube/cube_3/border_line', ' ', True),
            ('cube/cube_4/border_line', ' ', True),
            ('cube/cube_5/border_line', ' ', True)
        ]
        self.assertEqual(expected, sorted(list(self.publish_queue._queue)))
        self.mock_callback.assert_called_once_with("01", True)

    async def test_guess_last_tiles_long_word(self):
        """Test guess_last_tiles with a word longer than 2 letters."""
        # Mock the callback
        self.mock_callback = AsyncMock()
        cubes_to_game.guess_tiles_callback = self.mock_callback
        
        cubes_to_game.tiles_to_cubes = {
            "0": "cube_0",
            "1": "cube_1",
            "2": "cube_2",
            "3": "cube_3",
            "4": "cube_4",
            "5": "cube_5"
        }
        cubes_to_game.last_guess_tiles = ["0123"]
        await cubes_to_game.guess_last_tiles(self.publish_queue)
        
        expected = [
            ('cube/cube_0/border_line', '[', True),  # Start marker
            ('cube/cube_1/border_line', '-', True),  # Middle marker
            ('cube/cube_2/border_line', '-', True),  # Middle marker
            ('cube/cube_3/border_line', ']', True),  # End marker
            ('cube/cube_4/border_line', ' ', True),
            ('cube/cube_5/border_line', ' ', True)
        ]
        self.assertEqual(expected, sorted(list(self.publish_queue._queue)))
        self.mock_callback.assert_called_once_with("0123", True)

    async def test_guess_last_tiles_multiple_words(self):
        """Test guess_last_tiles with multiple words of different lengths."""
        # Mock the callback
        self.mock_callback = AsyncMock()
        cubes_to_game.guess_tiles_callback = self.mock_callback
        
        cubes_to_game.tiles_to_cubes = {
            "0": "cube_0",
            "1": "cube_1",
            "2": "cube_2",
            "3": "cube_3",
            "4": "cube_4",
            "5": "cube_5"
        }
        cubes_to_game.last_guess_tiles = ["01", "234"]  # One 2-letter word and one 3-letter word
        await cubes_to_game.guess_last_tiles(self.publish_queue)
        
        expected = [
            ('cube/cube_0/border_line', '[', True),  # First word start
            ('cube/cube_1/border_line', ']', True),  # First word end
            ('cube/cube_2/border_line', '[', True),  # Second word start
            ('cube/cube_3/border_line', '-', True),  # Second word middle
            ('cube/cube_4/border_line', ']', True),  # Second word end
            ('cube/cube_5/border_line', ' ', True)   # Unused
        ]
        self.assertEqual(expected, sorted(list(self.publish_queue._queue)))
        
        # Verify callback called for each word
        self.assertEqual(2, self.mock_callback.call_count)
        self.mock_callback.assert_any_call("01", True)
        self.mock_callback.assert_any_call("234", True)

    async def test_flash_good_words(self):
        cubes_to_game.tiles_to_cubes = {
            "1" : "cube_1",
            "2" : "cube_2",
            "3" : "cube_3"
        }
        await cubes_to_game.good_guess(self.publish_queue, list("123"))
        expected = [('cube/cube_1/flash', None, True),
            ('cube/cube_1/border_color', 'G', True),
            ('cube/cube_2/flash', None, True),
            ('cube/cube_2/border_color', 'G', True),
            ('cube/cube_3/flash', None, True),
            ('cube/cube_3/border_color', 'G', True)]
        self.assertEqual(expected,
            list(self.publish_queue._queue))

class Message:
    def __init__(self, topic):
        self.topic = topic
        self.topic_ix = 0

class Client:
    def __init__(self, messages):
        self.published = []
        self.messages = self._messages_iter(messages)

    async def _messages_iter(self, messages):
        for message in messages:
            yield message

    async def publish(self, topic, *payload):
        self.published.append((topic, *payload))

if __name__ == '__main__':
    unittest.main()
