import unittest
from core.player_mapping import calculate_player_mapping

class TestPlayerMapping(unittest.TestCase):
    def test_no_started_sets_returns_defaults(self):
        # Case: Keyboard mode or no hardware detected
        # Should return default mapping (usually 0:0, 1:1)
        mapping = calculate_player_mapping([])
        self.assertEqual(mapping, {0: 0, 1: 1})

    def test_single_player_identity_mapping(self):
        # Case: Only Set 1 starts (e.g. Player 1 hardware)
        # Should map Player 1 -> Set 1 (Identity)
        mapping = calculate_player_mapping([1])
        self.assertEqual(mapping, {1: 1})
        
        # Case: Only Set 0 starts
        mapping = calculate_player_mapping([0])
        self.assertEqual(mapping, {0: 0})
        
        # Case: Only Set 2 starts (hypothetically)
        mapping = calculate_player_mapping([2])
        self.assertEqual(mapping, {2: 2})

    def test_multi_player_sequential_mapping(self):
        # Case: Set 0 and Set 1 start
        # Should map 0->0, 1->1
        mapping = calculate_player_mapping([0, 1])
        self.assertEqual(mapping, {0: 0, 1: 1})

    def test_multi_player_sequential_mapping_order_independence(self):
        # Case: Set 1 and Set 0 start (order shouldn't matter)
        mapping = calculate_player_mapping([1, 0])
        self.assertEqual(mapping, {0: 0, 1: 1})

    def test_multi_player_sequential_mapping_arbitrary_ids(self):
        # Case: Set 2 and Set 5 start
        # Should map Player 0 -> Set 2, Player 1 -> Set 5
        mapping = calculate_player_mapping([5, 2])
        self.assertEqual(mapping, {0: 2, 1: 5})

if __name__ == '__main__':
    unittest.main()
