#! /usr/bin/env python

import unittest
import pygame
import pygame.freetype
from textrect import TextRectException, FontRectGetter, Blitter, TextRectRenderer

class TestPrerenderTextrect(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.font = pygame.freetype.SysFont(None, 24)  # Using default font for testing
        self.rect = pygame.Rect(0, 0, 200, 500)
        self.color = pygame.Color(255, 255, 255)
        self.renderer = TextRectRenderer(self.font, self.rect, self.color)
        
    def test_simple_text(self):
        """Test basic text that fits within bounds"""
        rect = pygame.Rect(0, 0, 200, 100)
        words = ["Hello", "World"]
        colors = [pygame.Color(255, 255, 255)] * len(words)
        
        self.renderer._rect = rect
        pos_dict = self.renderer._prerender_textrect(words)
        
        # First word should be at origin
        self.assertEqual(pos_dict["Hello"], (0, 0))
        
        # Second word should be to the right of first word
        self.assertTrue(pos_dict["World"][0] > pos_dict["Hello"][0])
        self.assertEqual(pos_dict["World"][1], 0)  # Same line
        
    def test_word_wrap(self):
        """Test that words wrap to next line when they exceed width"""
        rect = pygame.Rect(0, 0, 100, 100)
        words = ["Hello", "World"]
        colors = [pygame.Color(255, 255, 255)] * len(words)
        
        self.renderer._rect = rect
        pos_dict = self.renderer._prerender_textrect(words)
        
        # First word at origin
        self.assertEqual(pos_dict["Hello"], (0, 0))
        
        # Second word should wrap to next line
        self.assertEqual(pos_dict["World"][0], 0)
        self.assertTrue(pos_dict["World"][1] > 0)
        
    def test_empty_text(self):
        """Test handling of empty text"""
        words = []
        colors = []
        pos_dict = self.renderer._prerender_textrect(words)
        self.assertEqual(pos_dict, {})
        
    def test_word_too_long(self):
        """Test error when word is too long to fit"""
        rect = pygame.Rect(0, 0, 10, 100)  # Very narrow rect
        words = ["ThisWordIsTooLong"]
        colors = [pygame.Color(255, 255, 255)]
        
        self.renderer._rect = rect
        with self.assertRaises(TextRectException):
            self.renderer._prerender_textrect(words)
            
    def test_multiple_lines(self):
        """Test text that spans multiple lines"""
        rect = pygame.Rect(0, 0, 100, 200)
        words = ["One", "Two", "Three", "Four"]
        colors = [pygame.Color(255, 255, 255)] * len(words)
        
        self.renderer._rect = rect
        pos_dict = self.renderer._prerender_textrect(words)
        
        # Verify words are positioned correctly
        self.assertEqual(pos_dict["One"], (0, 0))  # First word at origin
        
        # Verify subsequent words are either on same line (if they fit) or next line
        last_y = 0
        for word in words[1:]:
            if pos_dict[word][0] == 0:  # Word starts at left margin
                self.assertTrue(pos_dict[word][1] > last_y)  # Must be on a new line
                last_y = pos_dict[word][1]
            else:
                self.assertEqual(pos_dict[word][1], last_y)  # Must be on same line
        
    def test_renderer(self):
        """Test the TextRectRenderer"""
        words = ["Hello", "World"]
        colors = [pygame.Color(255, 255, 255)] * len(words)
        surface = self.renderer.render(words, colors)
        self.assertIsInstance(surface, pygame.Surface)
        
    def test_get_pos(self):
        """Test getting position for a specific word"""
        words = ["Hello", "World"]
        colors = [pygame.Color(255, 255, 255)] * len(words)
        self.renderer.render(words, colors)  # Need to render first to populate pos_dict
        pos = self.renderer.get_pos("Hello")
        self.assertEqual(pos, (0, 0))  # First word should be at origin

    def tearDown(self):
        pygame.quit()

if __name__ == '__main__':
    unittest.main() 