#! /usr/bin/env python

import functools
import pygame
import pygame.freetype
import math
import random
# https://www.pygame.org/pcr/text_rect/index.php

VICTORY_PALETTE = [
    pygame.Color("gold"),
    pygame.Color("white"),
    pygame.Color("cyan"),
    pygame.Color("magenta"),
    pygame.Color("orange")
]

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
    def _get_size(font: pygame.freetype.Font, text: str) -> tuple[int, int]:
        r = font.get_rect(text)
        return r.width, r.height

    def get_size(self, text: str) -> tuple[int, int]:
        return self._get_size(self._font, text)

class Blitter():
    def __init__(self, font: pygame.freetype.Font, rect: pygame.Rect) -> None:
        self._font = font
        self._rect = rect
        self._empty_surface = pygame.Surface(rect.size, pygame.SRCALPHA)

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def _render_word(font: pygame.freetype.Font, word: str, color_tuple: tuple[int, int, int, int]) -> pygame.Surface:
        return font.render(word, pygame.Color(color_tuple))[0]

    def _render_blit_xy(self, surface: pygame.Surface, font: pygame.freetype.Font, word: str, x: int, y: int, color: pygame.Color) -> None:
        color_obj = pygame.Color(color.r, color.g, color.b, color.a)
        surface.blit(self._render_word(font, word, (color_obj.r, color_obj.g, color_obj.b, color_obj.a)), (x, y))

    def blit_words(self, words: tuple[str], pos_dict: dict[str, tuple[int, int]], colors: list[pygame.Color], animation_time: float = 0.0, animate: bool = False) -> pygame.Surface:
        surface = self._empty_surface.copy()
        
        for i, (word, color) in enumerate(zip(words, colors)):
            x, y = pos_dict[word]
            
            if animate:
                # Festive Color Cycling
                # Palette index cycles or shifts
                palette_index = int(animation_time * 2 + i) % len(VICTORY_PALETTE)
                festive_color = VICTORY_PALETTE[palette_index]
                self._render_blit_xy(surface, self._font, word, x, y, festive_color)
            else:
                 self._render_blit_xy(surface, self._font, word, x, y, color)
            
        return surface

class TextRectRenderer():
    def __init__(self, font: pygame.freetype.Font, rect: pygame.Rect) -> None:
        self._font = font
        self._rect = rect
        self._font_rect_getter = FontRectGetter(font)
        self._blitter = Blitter(font, rect)
        self._pos_dict = {}
        self._space_width = int(self._font_rect_getter.get_size("I")[0]*1.5)
        x_height = self._font_rect_getter.get_size("X")[1]
        self._vertical_gap = int(1.25 * x_height)
        self._vertical_gap = int(1.25 * x_height)
        self.animation_time = 0.0

    def reset_animation(self) -> None:
        """Reset the animation phase."""
        self.animation_time = 0.0

    def update_pos_dict(self, words: list[str]) -> None:
        self._pos_dict = self._prerender_textrect(words)

    def render(self, words: list[str], colors: list[pygame.Color], animate: bool = False) -> pygame.Surface:
        self.update_pos_dict(words)
        
        if animate:
            # Advance animation time
            self.animation_time += 0.05
        
        return self._blitter.blit_words(words, self._pos_dict, colors, self.animation_time, animate=animate)

    def get_pos(self, word: str) -> tuple[int, int]:
        return self._pos_dict[word]

    def _prerender_textrect(self, words: list[str]) -> dict[str, tuple[int, int]]:
        pos_dict = {}
        if not words:
            return pos_dict

        pos_dict[words[0]] = (0, 0)
        last_x, last_y = 0, 0
        last_width = self._font_rect_getter.get_size(words[0])[0]

        for word in words[1:]:
            word_width, _ = self._font_rect_getter.get_size(word)
            if word_width > self._rect.width:
                raise TextRectException("The word " + word + " is too long to fit in the rect passed.")
            
            next_x = last_x + last_width + self._space_width
            
            if next_x + word_width < self._rect.width:
                last_x, last_y = next_x, last_y
            else:
                new_y = last_y + self._vertical_gap
                last_x, last_y = 0, new_y
            pos_dict[word] = (last_x, last_y)
            last_width = word_width
                
        return pos_dict

def textrect_loop(trr, my_string):
    words = my_string.split()
    colors = [pygame.Color(216, 216, 216)] * len(words)
    for i in range(10000):
        trr.render(words, colors)

if __name__ == '__main__':
    import cProfile
    import pygame
    import pygame.font
    import pygame.freetype
    import sys
    from pygame.locals import QUIT, KEYDOWN

    pygame.init()

    display = pygame.display.set_mode((400, 400))

    my_font = pygame.freetype.Font(None, 22)

    my_string = "WAVES CRASHED VIOLENTLY AGAINST RUGGED CLIFFS WHILE SEAGULLS SOARED EFFORTLESSLY THROUGH GOLDEN SKIES AS DISTANT THUNDER ECHOED ACROSS VAST, EMPTY VALLEYS BENEATH TOWERING, SNOW-CAPPED MOUNTAINS SHIMMERING UNDER FADING TWILIGHT."

    my_rect = pygame.Rect((40, 40, 300, 400))
    trr = TextRectRenderer(my_font, my_rect)
    if len(sys.argv) > 1:
        cProfile.run('textrect_loop(trr, my_string)')
    words = my_string.split()
    colors = [pygame.Color(216, 216, 216)] * len(words)
    rendered_text = trr.render(words, colors)

    display.blit(rendered_text, my_rect.topleft)
    pygame.image.save(rendered_text, "textrect.png")

    if len(sys.argv) <= 1:
        pygame.display.update()

        while not pygame.event.wait().type in (QUIT, KEYDOWN):
            pass
