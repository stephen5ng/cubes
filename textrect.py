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

    def _render_blit(self, surface: pygame.Surface, line: str, height: int) -> pygame.Surface:
        surface.blit(self._font.render(line, self._color)[0], (0, height))
        return surface

    @functools.lru_cache(maxsize=64)
    def blit(self, lines: tuple[str], heights: tuple[int]) -> pygame.Surface:
        if len(lines) == 0:
            return pygame.Surface(self._rect.size, pygame.SRCALPHA)
        if len(lines) == 1:
            return self._render_blit(self.blit((), ()).copy(), lines[0], heights[0])

        previous_lines_surface = self.blit(tuple(lines[:-1]), tuple(heights[:-1])).copy()
        return self._render_blit(previous_lines_surface, lines[-1], heights[-1])

class TextRectRenderer():
    def __init__(self, font: pygame.freetype.Font, rect: pygame.Rect, color: pygame.Color) -> None:
        self._font = font
        self._rect = rect
        self._color = color
        self._font_rect_getter = FontRectGetter(font)
        self._blitter = Blitter(font, color, rect)

    def render(self, string: str) -> pygame.Surface:
        return render_textrect(string, self._blitter,self._rect, self._font_rect_getter)

    def get_last_rect(self, string: str) -> pygame.Rect:
        return get_last_textrect(string, self._rect, self._font_rect_getter)

def prerender_textrect(string: str, rect: pygame.Rect, rect_getter: FontRectGetter) -> tuple[pygame.Rect, tuple[str, ...], tuple[int, ...]]:
    final_lines = []
    last_rect = pygame.Rect()

    if rect_getter.get_rect(string).width > rect.width:
        words = string.split(' ')

        # if any of our words are too long to fit, return.
        for word in words:
            last_rect = rect_getter.get_rect(word)
            if last_rect.width >= rect.width:
                raise TextRectException("The word " + word + " is too long to fit in the rect passed.")

        # Start a new line
        accumulated_line = ""
        for word in words:
            test_line = accumulated_line + word + " "

            # Build the line while the words fit.
            if rect_getter.get_rect(test_line).width < rect.width:
                accumulated_line = test_line
            else:
                # Start a new line.
                final_lines.append(accumulated_line[:-1])
                last_rect = rect_getter.get_rect(accumulated_line[:-1])
                accumulated_line = word + " "
        final_lines.append(accumulated_line[:-1])
        last_rect = rect_getter.get_rect(accumulated_line[:-1])
    else:
        final_lines.append(string)
        last_rect = rect_getter.get_rect(string)

    accumulated_height = 0
    accumulated_lines = []
    heights = []
    for line in final_lines:
        accumulated_lines.append(line)
        heights.append(accumulated_height)
        line_rect = rect_getter.get_rect(line)
        if accumulated_height + line_rect.height >= rect.height:
            raise TextRectException("Once word-wrapped, the text string was too tall to fit in the rect.")
        last_rect.y = accumulated_height
        accumulated_height += line_rect.height + int(line_rect.height/3)

    last_rect.x = 0
    return last_rect, tuple(accumulated_lines), tuple(heights)

def render_textrect(string: str, blitter: Blitter, rect: pygame.Rect, rg: FontRectGetter) -> pygame.Surface:
    _, accumulated_lines, heights = prerender_textrect(string, rect, rg)
    return blitter.blit(accumulated_lines, heights)

def get_last_textrect(string: str, rect: pygame.Rect, rg: FontRectGetter) -> pygame.Rect:
    return prerender_textrect(string, rect, rg)[0]

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
