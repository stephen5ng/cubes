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
        r = self._font.get_rect(text)
        return pygame.Rect(0, 0, r.width, r.height)

class Blitter():
    def __init__(self, font: pygame.freetype.Font, color: pygame.Color, rect: pygame.Rect) -> None:
        self._font = font
        self._color = color
        self._rect = rect
        self._empty_surface = pygame.Surface(rect.size, pygame.SRCALPHA)

    @functools.lru_cache(maxsize=64)
    def _render_blit_xy(self, surface: pygame.Surface, line: str, x: int, y: int):
        surface.blit(self._font.render(line, self._color)[0], (x, y))

    def blit_words(self, words: tuple[str], rect_dict: dict[str, pygame.Rect]) -> pygame.Surface:
        if not words:
            return self._empty_surface.copy()
            
        surface = self._empty_surface.copy()
        for word in words:
            self._render_blit_xy(surface, word, rect_dict[word].x, rect_dict[word].y)
        return surface

class TextRectRenderer():
    def __init__(self, font: pygame.freetype.Font, rect: pygame.Rect, color: pygame.Color) -> None:
        self._font = font
        self._rect = rect
        self._color = color
        self._font_rect_getter = FontRectGetter(font)
        self._blitter = Blitter(font, color, rect)
        self._rect_dict = {}

    def render(self, words: list[str]) -> pygame.Surface:
        self._rect_dict = prerender_textrect(words, self._rect, self._font_rect_getter)
        return self._blitter.blit_words(tuple(words), self._rect_dict)

    def get_rect(self, word: str) -> pygame.Rect:
        return self._rect_dict[word]

def prerender_textrect(words: list[str], rect: pygame.Rect, rect_getter: FontRectGetter) -> dict[str, pygame.Rect]:
    rect_dict = {}
    if not words:
        return rect_dict

    # Check if any words are too long
    for word in words:
        if rect_getter.get_rect(word).width >= rect.width:
            raise TextRectException("The word " + word + " is too long to fit in the rect passed.")
        
    space_width = rect_getter.get_rect(" ").width
    space_height = rect_getter.get_rect("X").height
    
    last_rect = rect_getter.get_rect(words[0]).copy()
    rect_dict[words[0]] = last_rect
    
    for word in words[1:]:
        word_rect = rect_getter.get_rect(word).copy()
        last_x = last_rect.x + last_rect.width + space_width
        if last_x + word_rect.width < rect.width:
            word_rect.x = last_x
            word_rect.y = last_rect.y
        else:
            word_rect.x = 0
            word_rect.y = last_rect.y + last_rect.height + int(space_height/3)
        rect_dict[word] = word_rect
        last_rect = word_rect
            
    return rect_dict

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
    rendered_text = trr.render(my_string.split())

    display.blit(rendered_text, my_rect.topleft)
    pygame.image.save(rendered_text, "textrect.png")

    if len(sys.argv) <= 1:
        pygame.display.update()

        while not pygame.event.wait().type in (QUIT, KEYDOWN):
            pass
