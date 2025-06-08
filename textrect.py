#! /usr/bin/env python

import functools
import pygame
import pygame.freetype
# https://www.pygame.org/pcr/text_rect/index.php

class TextRectException(BaseException):
    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message

class FontRectGetter():
    def __init__(self, font: pygame.freetype.Font) -> None:
        self._font = font

    @functools.lru_cache(maxsize=64)
    def get_rect(self, text: str):
        return self._font.get_rect(text)

class Blitter():
    def __init__(self, font: pygame.freetype.Font, color: pygame.Color, rect: pygame.Rect) -> None:
        self._font = font
        self._color = color
        self._rect = rect
        self._empty_surface = pygame.Surface(rect.size, pygame.SRCALPHA)

    def _render_blit(self, surface: pygame.Surface, line: str, height: int) -> pygame.Surface:
        surface.blit(self._font.render(line, self._color)[0], (0, height))
        return surface

    @functools.lru_cache(maxsize=64)
    def blit(self, lines: tuple[str], heights: tuple[int]) -> pygame.Surface:
        if not lines:
            return self._empty_surface.copy()
            
        surface = self._empty_surface.copy()
        for line, height in zip(lines, heights):
            self._render_blit(surface, line, height)
        return surface

class TextRectRenderer():
    def __init__(self, font: pygame.freetype.Font, rect: pygame.Rect, color: pygame.Color) -> None:
        self._font = font
        self._rect = rect
        self._color = color
        self._font_rect_getter = FontRectGetter(font)
        self._blitter = Blitter(font, color, rect)

    def render(self, string: str) -> pygame.Surface:
        _, accumulated_lines, heights = prerender_textrect(string, self._rect, self._font_rect_getter)
        return self._blitter.blit(accumulated_lines, heights)

    def get_last_rect(self, string: str) -> pygame.Rect:
        return prerender_textrect(string, self._rect, self._font_rect_getter)[0]

def wrap_lines(words: list[str], rect_width: int, rect_getter: FontRectGetter) -> list[str]:
    final_lines = []
    accumulated_line = ""
    for word in words:
        test_line = accumulated_line + word + " "

        # Build the line while the words fit.
        if rect_getter.get_rect(test_line).width < rect_width:
            accumulated_line = test_line
        else:
            # Start a new line.
            final_lines.append(accumulated_line[:-1])
            accumulated_line = word + " "
    final_lines.append(accumulated_line[:-1])
    return final_lines

def calculate_line_heights(lines: list[str], rect_height: int, rect_getter: FontRectGetter) -> list[int]:
    accumulated_height = 0
    heights = []
    for line in lines:
        heights.append(accumulated_height)
        line_rect = rect_getter.get_rect(line)
        if accumulated_height + line_rect.height >= rect_height:
            raise TextRectException("Once word-wrapped, the text string was too tall to fit in the rect.")
        accumulated_height += line_rect.height + int(line_rect.height/3)
    return heights

def prerender_textrect(string: str, rect: pygame.Rect, rect_getter: FontRectGetter) -> tuple[pygame.Rect, tuple[str, ...], tuple[int, ...]]:
    words = string.split(' ') if rect_getter.get_rect(string).width > rect.width else [string]

    # if any of our words are too long to fit, return.
    for word in words:
        if rect_getter.get_rect(word).width >= rect.width:
            raise TextRectException("The word " + word + " is too long to fit in the rect passed.")

    final_lines = wrap_lines(words, rect.width, rect_getter)
    heights = calculate_line_heights(final_lines, rect.height, rect_getter)

    # Calculate final rect from last line
    last_rect = rect_getter.get_rect(final_lines[-1])
    last_rect.y = heights[-1]
    last_rect.x = 0
    return last_rect, tuple(final_lines), tuple(heights)

def textrect_loop(trr, my_string):
    for i in range(1000):
        trr.render(my_string)

if __name__ == '__main__':
    import cProfile
    import pygame
    import pygame.font
    import pygame.freetype
    import sys
    from pygame.locals import *

    pygame.init()

    display = pygame.display.set_mode((400, 400))

    my_font = pygame.freetype.Font(None, 22)

    my_string = "Hi there! I'm a nice bit of wordwrapped text. Won't you be my friend? Honestly, wordwrapping is easy, with David's fancy new render_textrect () function. This is a new line. This is another one. Another line, you lucky dog."

    my_rect = pygame.Rect((40, 40, 300, 400))
    trr = TextRectRenderer(my_font, my_rect, pygame.Color(216, 216, 216))
    cProfile.run('textrect_loop(trr, my_string)')
    rendered_text = trr.render(my_string)

    display.blit(rendered_text, my_rect.topleft)
    pygame.image.save(rendered_text, "textrect.png")

    if len(sys.argv) <= 1:
        pygame.display.update()

        while not pygame.event.wait().type in (QUIT, KEYDOWN):
            pass
