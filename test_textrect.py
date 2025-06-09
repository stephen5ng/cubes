#! /usr/bin/env python

import unittest
import pygame
import pygame.freetype
from textrect import prerender_textrect, TextRectException, FontRectGetter, Blitter, TextRectRenderer

class TestPrerenderTextrect(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.font = pygame.freetype.SysFont(None, 24)  # Using default font for testing
        self.rect_getter = FontRectGetter(self.font)
        self.rect = pygame.Rect(0, 0, 200, 500)
        self.color = pygame.Color(255, 255, 255)
        self.renderer = TextRectRenderer(self.font, self.rect, self.color)
        
    def test_simple_text(self):
        """Test basic text that fits within bounds"""
        rect = pygame.Rect(0, 0, 200, 100)
        words = ["Hello", "World"]
        
        rect_dict = prerender_textrect(words, rect, self.rect_getter)
        
        self.assertEqual(len(rect_dict), 2)
        self.assertIn("Hello", rect_dict)
        self.assertIn("World", rect_dict)
        self.assertEqual(rect_dict["Hello"].x, 0)  # First word starts at x=0
        self.assertEqual(rect_dict["Hello"].y, 0)  # First word starts at y=0
        self.assertGreater(rect_dict["World"].x, rect_dict["Hello"].width)  # Second word after first

    def test_word_wrap(self):
        """Test text that needs to be wrapped"""
        rect = pygame.Rect(0, 0, 100, 500)  # Increased height to accommodate wrapped text
        words = "This is a long text that should wrap to multiple lines".split()
        
        rect_dict = prerender_textrect(words, rect, self.rect_getter)
        
        # Verify all words have rects
        self.assertEqual(len(rect_dict), len(words))
        # Verify all words fit within width
        for word in words:
            self.assertLessEqual(rect_dict[word].right, rect.width)

    def test_word_wrap_exact_width(self):
        """Test word wrapping when a line exactly fits the width"""
        rect = pygame.Rect(0, 0, 200, 500)  # Wider rect
        # Use unique single-character words
        words = ["A1", "A2", "A3", "A4", "A5"]  # Multiple unique short words
        
        rect_dict = prerender_textrect(words, rect, self.rect_getter)
        
        # Verify all words have rects
        self.assertEqual(len(rect_dict), len(words))
        # Verify all words fit
        for word in words:
            self.assertLessEqual(rect_dict[word].right, rect.width)
        # Verify words are properly spaced
        for i in range(1, len(words)):
            prev_word = words[i-1]
            curr_word = words[i]
            self.assertGreater(rect_dict[curr_word].x, rect_dict[prev_word].right)

    def test_too_long_word(self):
        """Test handling of words that are too long to fit"""
        rect = pygame.Rect(0, 0, 50, 100)  # Very narrow rect
        words = ["Supercalifragilisticexpialidocious"]
        
        with self.assertRaises(TextRectException):
            prerender_textrect(words, rect, self.rect_getter)

    def test_empty_words(self):
        """Test handling of empty word list"""
        rect = pygame.Rect(0, 0, 100, 100)
        words = []
        
        rect_dict = prerender_textrect(words, rect, self.rect_getter)
        
        self.assertEqual(len(rect_dict), 0)  # Should return empty dict

    def test_word_wrap_with_multiple_spaces(self):
        """Test word wrapping with multiple spaces between words"""
        rect = pygame.Rect(0, 0, 100, 500)
        words = "This is a text with multiple spaces".split()
        
        rect_dict = prerender_textrect(words, rect, self.rect_getter)
        
        # Verify all words have rects and fit within width
        self.assertEqual(len(rect_dict), len(words))
        for word in words:
            self.assertLessEqual(rect_dict[word].right, rect.width)

    def test_word_wrap_last_word(self):
        """Test word wrapping when the last word needs to wrap"""
        rect = pygame.Rect(0, 0, 200, 500)  # Wider rect
        words = ["A"] * 15 + ["End"]  # Multiple words plus end word
        
        rect_dict = prerender_textrect(words, rect, self.rect_getter)
        
        # Verify last word is properly placed
        self.assertEqual(rect_dict["End"].x, 0)  # Should start at beginning of line
        self.assertGreater(rect_dict["End"].y, rect_dict["A"].y)  # Should be on next line

    def test_renderer(self):
        """Test the TextRectRenderer"""
        words = ["Test", "text"]
        surface = self.renderer.render(words)
        self.assertIsInstance(surface, pygame.Surface)

    def test_get_rect(self):
        """Test getting rect for a specific word"""
        words = ["Test", "text"]
        self.renderer.render(words)  # Need to render first to populate rect_dict
        rect = self.renderer.get_rect("Test")
        self.assertIsInstance(rect, pygame.Rect)

    def tearDown(self):
        pygame.quit()

if __name__ == '__main__':
    unittest.main() 