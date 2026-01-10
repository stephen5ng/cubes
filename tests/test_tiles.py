#!/usr/bin/env python3

import random
import unittest

from core import tiles

class TestRack(unittest.TestCase):
    def setUp(self):
        tiles.MAX_LETTERS = 7
        random.seed(1)

    def test_replace_letter(self) -> None:
        rack = tiles.Rack("FRIENDS")
        replaced = rack.replace_letter("Z", 3)
        self.assertEqual(tiles.Tile('Z', '3'), replaced)
        self.assertEqual("FRIZNDS", rack.letters())

    def test_letters_to_ids(self) -> None:
        rack = tiles.Rack("FRIENDS")
        self.assertEqual(['3', '4', '5'], rack.letters_to_ids("END"))
        self.assertEqual(['3', '4', '5'], rack.letters_to_ids("EEND"))
        self.assertEqual(['3', '4', '5'], rack.letters_to_ids("ENZD"))

    def test_ids_to_letters(self) -> None:
        rack = tiles.Rack("FRIENDS")
        self.assertEqual('END', rack.ids_to_letters(list("345")))
    
    def test_gen_next_letter_deterministic(self) -> None:
        """Test that get_next_letter is deterministic with same random state."""
        from core.tile_generator import TileGenerator
        generator = TileGenerator()
        
        # We need to control the global random state since TileGenerator uses it
        state = random.getstate()
        random.seed(42)
        letter1 = generator.get_next_letter("ABCDEF")
        
        random.setstate(state)
        random.seed(42)
        letter2 = generator.get_next_letter("ABCDEF")
        
        self.assertEqual(letter1, letter2)
    
    def test_gen_next_letter_returns_uppercase(self) -> None:
        """Test that get_next_letter returns an uppercase letter."""
        from core.tile_generator import TileGenerator
        generator = TileGenerator()
        letter = generator.get_next_letter("ABCDEF")
        self.assertTrue(letter.isupper())
        self.assertEqual(len(letter), 1)

if __name__ == '__main__':
    unittest.main()
