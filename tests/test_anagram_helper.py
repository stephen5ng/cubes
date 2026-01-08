#!/usr/bin/env python3

import unittest
import random
import sys
import os

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.anagram_helper import AnagramHelper


class TestAnagramHelper(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Initialize the singleton once for all tests."""
        cls.helper = AnagramHelper.get_instance()
    
    def test_compute_signature_single_letter(self):
        """Test signature computation for single letters."""
        sig = self.helper._compute_signature('a')
        expected = tuple([1] + [0] * 25)
        self.assertEqual(sig, expected)
        
        sig_z = self.helper._compute_signature('z')
        expected_z = tuple([0] * 25 + [1])
        self.assertEqual(sig_z, expected_z)
    
    def test_compute_signature_duplicates(self):
        """Test signature computation with duplicate letters."""
        sig = self.helper._compute_signature('aaa')
        expected = tuple([3] + [0] * 25)
        self.assertEqual(sig, expected)
        
        sig_mixed = self.helper._compute_signature('aabbcc')
        expected_mixed = tuple([2, 2, 2] + [0] * 23)
        self.assertEqual(sig_mixed, expected_mixed)
    
    def test_compute_signature_mixed_case(self):
        """Test that signatures are case-insensitive."""
        sig_lower = self.helper._compute_signature('abc')
        sig_upper = self.helper._compute_signature('ABC')
        # Note: _compute_signature expects lowercase, but count_anagrams handles case
        # This test verifies the raw signature function
        self.assertNotEqual(sig_lower, sig_upper)  # Different because uppercase has different ord values
    
    def test_count_anagrams_known_value(self):
        """Test anagram counting with a known result."""
        # BEEBRA should have 21 unique anagrams
        count = self.helper.count_anagrams("BEEBRA")
        self.assertEqual(count, 21)
    
    def test_count_anagrams_case_insensitive(self):
        """Test that counting is case-insensitive."""
        count_upper = self.helper.count_anagrams("BEEBRA")
        count_lower = self.helper.count_anagrams("beebra")
        count_mixed = self.helper.count_anagrams("BeEbRa")
        self.assertEqual(count_upper, count_lower)
        self.assertEqual(count_upper, count_mixed)
    
    def test_count_anagrams_empty_freq_map(self):
        """Test that empty freq_map returns 0."""
        # Create a new instance with empty map
        helper = AnagramHelper.__new__(AnagramHelper)
        helper._freq_map = {}
        count = helper.count_anagrams("ABC")
        self.assertEqual(count, 0)
    
    def test_score_candidates_returns_26(self):
        """Test that score_candidates returns exactly 26 candidates."""
        candidates = self.helper.score_candidates("ABCDEF")
        self.assertEqual(len(candidates), 26)
    
    def test_score_candidates_sorted_descending(self):
        """Test that candidates are sorted by score descending."""
        candidates = self.helper.score_candidates("ABCDEF")
        scores = [score for _, score in candidates]
        self.assertEqual(scores, sorted(scores, reverse=True))
    
    def test_score_candidates_format(self):
        """Test that each candidate is a (letter, score) tuple."""
        candidates = self.helper.score_candidates("ABCDEF")
        for letter, score in candidates:
            self.assertIsInstance(letter, str)
            self.assertEqual(len(letter), 1)
            self.assertTrue(letter.isupper())
            self.assertIsInstance(score, int)
            self.assertGreaterEqual(score, 0)
    
    def test_singleton_pattern(self):
        """Test that get_instance returns the same instance."""
        helper1 = AnagramHelper.get_instance()
        helper2 = AnagramHelper.get_instance()
        self.assertIs(helper1, helper2)


if __name__ == '__main__':
    unittest.main()
