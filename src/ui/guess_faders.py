"""Fading animations for guess feedback."""

import easing_functions
import functools
import pygame
import pygame.freetype

from utils import textrect
from src.rendering.animations import get_alpha


class LastGuessFader:
    """Handles fading animation for a single guess display."""

    FADE_DURATION_MS = 2000

    def __init__(self, last_update_ms: int, duration: int, surface: pygame.Surface, position: tuple[int, int]) -> None:
        self.last_update_ms = last_update_ms
        self.duration = duration
        self.easing = easing_functions.QuinticEaseInOut(start=0, end=255, duration=1)
        self.last_guess = ""
        self.last_guess_surface = surface
        self.last_guess_position = position
        self.alpha = 1

    def blit(self, target: pygame.Surface, now: int) -> None:
        """Render the fading surface to the target at the current time."""
        self.alpha = get_alpha(self.easing, self.last_update_ms, self.duration, now)
        if self.alpha:
            self.last_guess_surface.set_alpha(self.alpha)
            target.blit(self.last_guess_surface, self.last_guess_position)


class FaderManager:
    """Manages creation of faders for guess displays."""

    def __init__(self, previous_guesses: list[str], font: pygame.freetype.Font, text_rect_renderer: textrect.TextRectRenderer):
        self._previous_guesses = previous_guesses
        self._text_rect_renderer = text_rect_renderer
        self._font = font

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def _cached_render(font: pygame.freetype.Font, text: str, color_rgb: tuple[int, int, int]) -> pygame.Surface:
        """Cache rendered text surfaces for performance."""
        return font.render(text, pygame.Color(*color_rgb))[0]

    def create_fader(self, last_guess: str, last_update_ms: int, duration: int, color: pygame.Color) -> LastGuessFader:
        """Create a new fader for the given guess."""
        last_guess_surface = self._cached_render(self._font, last_guess, (color.r, color.g, color.b))
        last_guess_position = self._text_rect_renderer.get_pos(last_guess)
        return LastGuessFader(last_update_ms, duration, last_guess_surface, last_guess_position)
