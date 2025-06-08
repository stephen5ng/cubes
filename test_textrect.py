#! /usr/bin/env python

import unittest
import pygame
import pygame.freetype
from textrect import prerender_textrect, TextRectException, FontRectGetter, render_textrect, get_last_textrect, Blitter

class TestPrerenderTextrect(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.font = pygame.freetype.SysFont(None, 24)  # Using default font for testing
        self.rect_getter = FontRectGetter(self.font)
        self.rect = pygame.Rect(0, 0, 200, 500)
        self.blitter = Blitter(self.font, pygame.Color(255, 255, 255), self.rect)
        
    def test_simple_text(self):
        """Test basic text that fits within bounds"""
        rect = pygame.Rect(0, 0, 200, 100)
        text = "Hello World"
        
        last_rect, lines, heights = prerender_textrect(text, rect, self.rect_getter)
        
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "Hello World")
        self.assertEqual(heights[0], 0)
        self.assertIsInstance(last_rect, pygame.Rect)
        self.assertEqual(last_rect.x, 0)  # Test x position is set

    def test_word_wrap(self):
        """Test text that needs to be wrapped"""
        rect = pygame.Rect(0, 0, 100, 500)  # Increased height to accommodate wrapped text
        text = "This is a long text that should wrap to multiple lines"
        
        last_rect, lines, heights = prerender_textrect(text, rect, self.rect_getter)
        
        self.assertGreater(len(lines), 1)  # Should be multiple lines
        self.assertEqual(len(lines), len(heights))  # Should have matching heights
        # Verify the last line is properly wrapped
        self.assertLess(self.rect_getter.get_rect(lines[-1]).width, rect.width)

    def test_word_wrap_exact_width(self):
        """Test word wrapping when a line exactly fits the width"""
        rect = pygame.Rect(0, 0, 200, 500)
        # First get a line that fits exactly
        text = "A " * 20  # Start with something that will need to wrap
        test_line = ""
        for word in text.split():
            if self.rect_getter.get_rect(test_line + word + " ").width < rect.width:
                test_line += word + " "
        test_line = test_line.rstrip()  # Remove trailing space before testing
        
        last_rect, lines, heights = prerender_textrect(test_line, rect, self.rect_getter)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], test_line)

    def test_newlines(self):
        """Test text with explicit newlines"""
        rect = pygame.Rect(0, 0, 200, 200)
        text = "Line 1\nLine 2\nLine 3"
        
        last_rect, lines, heights = prerender_textrect(text, rect, self.rect_getter)
        
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "Line 1")
        self.assertEqual(lines[1], "Line 2")
        self.assertEqual(lines[2], "Line 3")
        # Test that heights are properly incremented
        self.assertLess(heights[0], heights[1])
        self.assertLess(heights[1], heights[2])

    def test_too_long_word(self):
        """Test handling of words that are too long to fit"""
        rect = pygame.Rect(0, 0, 50, 100)  # Very narrow rect
        text = "Supercalifragilisticexpialidocious"
        
        with self.assertRaises(TextRectException):
            prerender_textrect(text, rect, self.rect_getter)

    def test_too_tall_text(self):
        """Test handling of text that's too tall for the rect"""
        rect = pygame.Rect(0, 0, 100, 10)  # Very short rect
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        
        with self.assertRaises(TextRectException):
            prerender_textrect(text, rect, self.rect_getter)

    def test_empty_string(self):
        """Test handling of empty string"""
        rect = pygame.Rect(0, 0, 100, 100)
        text = ""
        
        last_rect, lines, heights = prerender_textrect(text, rect, self.rect_getter)
        
        self.assertEqual(len(lines), 0)
        self.assertEqual(len(heights), 0)
        self.assertIsInstance(last_rect, pygame.Rect)

    def test_multiple_consecutive_newlines(self):
        """Test handling of multiple consecutive newlines"""
        rect = pygame.Rect(0, 0, 200, 200)
        text = "Line 1\n\n\nLine 2"
        
        last_rect, lines, heights = prerender_textrect(text, rect, self.rect_getter)
        
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0], "Line 1")
        self.assertEqual(lines[1], "")
        self.assertEqual(lines[2], "")
        self.assertEqual(lines[3], "Line 2")

    def test_word_wrap_with_multiple_spaces(self):
        """Test word wrapping with multiple spaces between words"""
        rect = pygame.Rect(0, 0, 100, 500)
        text = "This    is    a    text    with    multiple    spaces"
        
        last_rect, lines, heights = prerender_textrect(text, rect, self.rect_getter)
        
        # Verify all lines are within width
        for line in lines:
            self.assertLess(self.rect_getter.get_rect(line).width, rect.width)

    def test_word_wrap_last_word(self):
        """Test word wrapping when the last word exactly fills a line"""
        rect = pygame.Rect(0, 0, 200, 500)  # Wider rect
        # Create text where last word needs to wrap
        text = "A " * 15 + "End"  # Shorter last word
        
        last_rect, lines, heights = prerender_textrect(text, rect, self.rect_getter)
        self.assertGreater(len(lines), 1)  # Should wrap to at least 2 lines
        self.assertEqual(lines[-1], "End")  # Last word should be on its own line

    def test_render_textrect(self):
        """Test the render_textrect function"""
        text = "Test text"
        surface = render_textrect(text, self.blitter, self.rect, self.rect_getter)
        self.assertIsInstance(surface, pygame.Surface)

    def test_get_last_textrect(self):
        """Test the get_last_textrect function"""
        text = "Test text"
        rect = get_last_textrect(text, self.rect, self.rect_getter)
        self.assertIsInstance(rect, pygame.Rect)

    def tearDown(self):
        pygame.quit()

if __name__ == '__main__':
    unittest.main() 