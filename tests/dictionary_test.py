#!/usr/bin/env python3

from io import StringIO
import random
import unittest

import dictionary

class TestDictionary(unittest.TestCase):
    def setUp(self) -> None:
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
        self.d = dictionary.Dictionary(3, 6, open=my_open)
        self.d.read("mock_file", "bingos_file")

    def testGetRack(self) -> None:
        self.assertEqual("ACEHRS", self.d.get_rack().letters())

    def testIsWord(self) -> None:
        self.assertTrue(self.d.is_word("ONLINE"))
        self.assertFalse(self.d.is_word("OXLINE"))


if __name__ == '__main__':
    unittest.main()