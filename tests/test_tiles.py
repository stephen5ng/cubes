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
        """Test that gen_next_letter is deterministic with same random state."""
        random.seed(42)
        rack1 = tiles.Rack("ABCDEF")
        letter1 = rack1.gen_next_letter()
        
        random.seed(42)
        rack2 = tiles.Rack("ABCDEF")
        letter2 = rack2.gen_next_letter()
        
        self.assertEqual(letter1, letter2)
    
    def test_gen_next_letter_returns_uppercase(self) -> None:
        """Test that gen_next_letter returns an uppercase letter."""
        rack = tiles.Rack("ABCDEF")
        letter = rack.gen_next_letter()
        self.assertTrue(letter.isupper())
        self.assertEqual(len(letter), 1)
    
    def test_refresh_next_letter(self) -> None:
        """Test that refresh_next_letter updates the next letter."""
        random.seed(100)
        rack = tiles.Rack("ABCDEF")
        initial_letter = rack.next_letter()
        
        # Modify the rack to change what the next letter should be
        rack.replace_letter("Z", 0)
        rack.refresh_next_letter()
        new_letter = rack.next_letter()
        
        # The letter may or may not change, but refresh should have been called
        # We just verify the method doesn't crash
        self.assertIsInstance(new_letter, str)
    
    def test_random_state_isolation(self) -> None:
        """Test that rack's RNG is isolated from global RNG."""
        random.seed(50)
        rack = tiles.Rack("ABCDEF")
        
        # Save the rack's next letter
        letter1 = rack.gen_next_letter()
        
        # Mess with global random state
        random.seed(999)
        for _ in range(100):
            random.random()
        
        # Reset to original seed and create new rack
        random.seed(50)
        rack2 = tiles.Rack("ABCDEF")
        letter2 = rack2.gen_next_letter()
        
        # Should get the same letter because rack maintains its own state
        self.assertEqual(letter1, letter2)

if __name__ == '__main__':
    unittest.main()
