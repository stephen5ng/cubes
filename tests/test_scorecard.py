#!/usr/bin/env python3

import unittest
from io import StringIO

from core import config
from core.dictionary import Dictionary
import random
from core.scorecard import ScoreCard
from core import tiles

class TestScoreCard(unittest.TestCase):
    def setUp(self):
        my_open = lambda filename, mode: StringIO("\n".join([
            "con",
            "tact",
            "contact",
            "service"
        ])) if filename == "sowpods.txt" else StringIO("\n".join([
            "contact", # ACCNOTT
            "service"
        ]))
        # Override config for this test
        config.MAX_LETTERS = 7
        random.seed(1)
        dictionary = Dictionary(config.MIN_LETTERS, config.MAX_LETTERS, open=my_open)
        dictionary.read("sowpods.txt", "bingos.txt")
        player_rack = dictionary.get_rack()
        self.score_card = ScoreCard(player_rack, dictionary)

    def test_guess(self):
        self.assertEqual(4, self.score_card.calculate_score("TACT"))

    def test_guess_bingo(self):
        self.assertEqual(17, self.score_card.calculate_score("CONTACT"))

    def test_score(self):
        self.assertEqual(4, self.score_card.calculate_score("TAIL"))
        self.assertEqual(3, self.score_card.calculate_score("QAT"))
        self.assertEqual(17, self.score_card.calculate_score("FRIENDS"))

    def test_update_previous_guesses(self):
        self.score_card.guesses = {(0, "CAT"), (0, "DOG")}
        self.score_card.player_rack = tiles.Rack("ABCDEFT")
        self.score_card.update_previous_guesses()
        self.assertEqual(set(["CAT"]), self.score_card.possible_words)

    def test_get_previous_guesses(self):
        self.score_card.possible_words = set(["CAT", "DOG"])
        self.assertEqual(["CAT", "DOG"],
            self.score_card.get_previous_guesses())

if __name__ == '__main__':
    unittest.main()
