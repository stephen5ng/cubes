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

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def _get_rect(font: pygame.freetype.Font, size: int, text: str) -> pygame.Rect:
        r = font.get_rect(text)
        return pygame.Rect(0, 0, r.width, r.height)

    def get_rect(self, text: str) -> pygame.Rect:
        return self._get_rect(self._font, self._font.size, text).copy()

class Blitter():
    def __init__(self, font: pygame.freetype.Font, color: pygame.Color, rect: pygame.Rect) -> None:
        self._font = font
        self._color = color
        self._rect = rect
        self._empty_surface = pygame.Surface(rect.size, pygame.SRCALPHA)

    def _render_blit_xy(self, surface: pygame.Surface, line: str, x: int, y: int, color_tuple: tuple[int, int, int, int]) -> None:
        surface.blit(self._font.render(line, pygame.Color(color_tuple))[0], (x, y))

    def blit_words(self, words: tuple[str], pos_dict: dict[str, tuple[int, int]], colors: list[pygame.Color]) -> pygame.Surface:
        if not words:
            return self._empty_surface.copy()
            
        surface = self._empty_surface.copy()
        for word, color in zip(words, colors):
            x, y = pos_dict[word]
            # Convert Color to hashable tuple
            color_tuple = (color.r, color.g, color.b, color.a)
            self._render_blit_xy(surface, word, x, y, color_tuple)
        return surface

class TextRectRenderer():
    def __init__(self, font: pygame.freetype.Font, rect: pygame.Rect, color: pygame.Color) -> None:
        self._font = font
        self._rect = rect
        self._color = color
        self._font_rect_getter = FontRectGetter(font)
        self._blitter = Blitter(font, color, rect)
        self._pos_dict = {}
        self._space_width = self._font_rect_getter.get_rect(" ").width
        self._space_height = self._font_rect_getter.get_rect("X").height

    def render(self, words: list[str], colors: list[pygame.Color]) -> pygame.Surface:
        self._pos_dict = self._prerender_textrect(words)
        return self._blitter.blit_words(words, self._pos_dict, colors)

    def get_pos(self, word: str) -> tuple[int, int]:
        return self._pos_dict[word]

    def _prerender_textrect(self, words: list[str]) -> dict[str, tuple[int, int]]:
        pos_dict = {}
        if not words:
            return pos_dict

        # Check if any words are too long
        for word in words:
            if self._font_rect_getter.get_rect(word).width >= self._rect.width:
                raise TextRectException("The word " + word + " is too long to fit in the rect passed.")
            
        # Position first word at origin
        last_rect = self._font_rect_getter.get_rect(words[0])
        pos_dict[words[0]] = (0, 0)
        
        for word in words[1:]:
            word_rect = self._font_rect_getter.get_rect(word)
            next_x = last_rect.x + last_rect.width + self._space_width
            
            if next_x + word_rect.width < self._rect.width:
                pos_dict[word] = (next_x, last_rect.y)
                word_rect.x, word_rect.y = next_x, last_rect.y
            else:
                new_y = last_rect.y + self._space_height + int(self._space_height/4)
                pos_dict[word] = (0, new_y)
                word_rect.x, word_rect.y = 0, new_y
                
            last_rect = word_rect
                
        return pos_dict

def textrect_loop(trr, my_string):
    words = my_string.split()
    colors = [pygame.Color(216, 216, 216)] * len(words)
    for i in range(1000):
        trr.render(words, colors)

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
    rendered_text = trr.render(my_string.split())

    display.blit(rendered_text, my_rect.topleft)
    pygame.image.save(rendered_text, "textrect.png")

    if len(sys.argv) <= 1:
        pygame.display.update()

        while not pygame.event.wait().type in (QUIT, KEYDOWN):
            pass
