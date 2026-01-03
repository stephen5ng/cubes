"""Display components for showing previous guesses."""

import pygame
import pygame.freetype

from utils import textrect
from src.config.display_constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    OLD_GUESS_COLOR, SHIELD_COLOR_P0, SHIELD_COLOR_P1,
    FADER_COLOR_P0, FADER_COLOR_P1, REMAINING_PREVIOUS_GUESSES_COLOR
)
from src.ui.guess_faders import FaderManager, LastGuessFader


class PreviousGuessesDisplayBase:
    """Base class for displaying previous guesses."""

    FONT = "Arial"

    def __init__(self, font_size: int) -> None:
        self.font = pygame.freetype.SysFont(PreviousGuessesDisplayBase.FONT, font_size)
        self.font.kerning = True
        self._text_rect_renderer = textrect.TextRectRenderer(self.font,
                pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))


class PreviousGuessesDisplay(PreviousGuessesDisplayBase):
    """Display for showing previous guesses with fading effects."""

    FONT_SIZE = 30
    POSITION_TOP = 24
    FADE_DURATION_NEW_GUESS = 2000
    FADE_DURATION_OLD_GUESS = 500
    PLAYER_COLORS = [SHIELD_COLOR_P0, SHIELD_COLOR_P1]  # Static array for player colors
    FADER_PLAYER_COLORS = [FADER_COLOR_P0, FADER_COLOR_P1]

    def __init__(self, font_size: int, guess_to_player: dict[str, int]) -> None:
        super().__init__(font_size)
        self.fader_inputs = []
        self.previous_guesses = []
        self.bloop_sound = pygame.mixer.Sound("./sounds/bloop.wav")
        self.bloop_sound.set_volume(0.2)
        self.guess_to_player = guess_to_player
        self.fader_manager = FaderManager(self.previous_guesses, self.font, self._text_rect_renderer)
        self.faders: list[LastGuessFader] = []
        self.draw()

    @classmethod
    def from_instance(cls, instance: 'PreviousGuessesDisplay', font_size: int, now_ms: int) -> 'PreviousGuessesDisplay':
        """Create a new instance from an existing one with a new font size."""
        new_instance = cls(font_size, instance.guess_to_player)
        new_instance.previous_guesses = instance.previous_guesses
        new_instance.fader_inputs = instance.fader_inputs
        new_instance.bloop_sound = instance.bloop_sound
        if instance.previous_guesses and instance.fader_inputs:
            new_instance._recreate_faders(now_ms)
        return new_instance

    def _try_add_fader(self, guess: str, color: pygame.Color, duration: int, now_ms: int) -> None:
        """Try to add a fader for the given guess if it exists in previous_guesses."""
        if guess in self.previous_guesses:
            fader = self.fader_manager.create_fader(guess, now_ms, duration, color)
            self.faders.append(fader)

    def _recreate_faders(self, now_ms: int) -> None:
        """Recreate all faders from stored inputs."""
        self.faders = []
        for last_guess, last_update_ms, color, duration in self.fader_inputs:
            self._try_add_fader(last_guess, color, duration, now_ms)

    def draw(self) -> None:
        """Draw the previous guesses display."""
        self.surface = self._text_rect_renderer.render(
            self.previous_guesses,
            [self.PLAYER_COLORS[self.guess_to_player.get(guess, 0)] for guess in self.previous_guesses])

    def old_guess(self, old_guess: str, now_ms: int) -> None:
        """Handle display of an old guess with fade effect."""
        self.fader_inputs.append(
            [old_guess, now_ms, OLD_GUESS_COLOR, PreviousGuessesDisplay.FADE_DURATION_OLD_GUESS])
        self._try_add_fader(old_guess,
                            OLD_GUESS_COLOR,
                            PreviousGuessesDisplay.FADE_DURATION_OLD_GUESS,
                            now_ms)
        self.draw()
        pygame.mixer.Sound.play(self.bloop_sound)

    def add_guess(self, previous_guesses: list[str], guess: str, player: int, now_ms: int) -> None:
        """Add a new guess and update the display."""
        self.fader_inputs.append(
            [guess, now_ms, self.FADER_PLAYER_COLORS[player], PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS])
        self.update_previous_guesses(previous_guesses, now_ms)
        self._try_add_fader(guess,
                            self.FADER_PLAYER_COLORS[player],
                            PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS,
                            now_ms)

    def new_guess(self, new_guess: str, player: int, now_ms: int) -> None:
        """Handle display of a new guess with fade effect."""
        fader_color = self.FADER_PLAYER_COLORS[player]
        self.fader_inputs.append(
            [new_guess, now_ms, fader_color, PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS])
        self._try_add_fader(new_guess,
                            fader_color,
                            PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS,
                            now_ms)

    def update_previous_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        """Update the list of previous guesses and refresh faders."""
        self.previous_guesses = previous_guesses
        self._text_rect_renderer.update_pos_dict(self.previous_guesses)
        self.fader_manager = FaderManager(self.previous_guesses, self.font, self._text_rect_renderer)
        self._recreate_faders(now_ms)
        self.draw()

    def update(self, window: pygame.Surface, now: int) -> None:
        """Render the display with faders to the window."""
        surface_with_faders = self.surface.copy()
        for fader in self.faders:
            fader.blit(surface_with_faders, now)

        # remove finished faders
        self.faders[:] = [f for f in self.faders if f.alpha]

        # remove finished faders from fader_inputs
        fader_guesses = [f.last_guess for f in self.faders]
        self.fader_inputs = [f for f in self.fader_inputs if f[0] in fader_guesses]

        window.blit(surface_with_faders, [0, PreviousGuessesDisplay.POSITION_TOP])


class RemainingPreviousGuessesDisplay(PreviousGuessesDisplayBase):
    """Display for showing remaining/unused previous guesses."""

    COLOR = pygame.Color("grey")
    TOP_GAP = 3
    PLAYER_COLORS = [pygame.Color(SHIELD_COLOR_P0.r, SHIELD_COLOR_P0.g, SHIELD_COLOR_P0.b, 192),
                     pygame.Color(SHIELD_COLOR_P1.r, SHIELD_COLOR_P1.g, SHIELD_COLOR_P1.b, 192)]  # Static array for player colors with 0.5 alpha

    def __init__(self, font_size: int, guess_to_player: dict[str, int]) -> None:
        super().__init__(font_size)
        self.guess_to_player = guess_to_player
        self.color = REMAINING_PREVIOUS_GUESSES_COLOR
        self.surface = pygame.Surface((0, 0))
        self.remaining_guesses = []

    @classmethod
    def from_instance(cls, instance: 'RemainingPreviousGuessesDisplay', font_size: int) -> 'RemainingPreviousGuessesDisplay':
        """Create a new instance from an existing one with a new font size."""
        new_instance = cls(font_size, instance.guess_to_player)
        new_instance.remaining_guesses = instance.remaining_guesses
        new_instance.color = instance.color
        return new_instance

    def update(self, window: pygame.Surface, height: int) -> None:
        """Render the display to the window at the appropriate position."""
        top = height + PreviousGuessesDisplay.POSITION_TOP + RemainingPreviousGuessesDisplay.TOP_GAP
        total_height = top + self.surface.get_bounding_rect().height
        if total_height > SCREEN_HEIGHT:
            raise textrect.TextRectException("can't update RemainingPreviousGuessesDisplay")
        window.blit(self.surface, [0, top])

    def update_remaining_guesses(self, remaining_guesses: list[str]) -> None:
        """Update the list of remaining previous guesses."""
        self.remaining_guesses = remaining_guesses
        self.draw()

    def draw(self) -> None:
        """Draw the remaining previous guesses display."""
        self.surface = self._text_rect_renderer.render(
            self.remaining_guesses,
            [self.PLAYER_COLORS[self.guess_to_player.get(guess, 0)] for guess in self.remaining_guesses])


class PreviousGuessesManager:
    """Manages previous guess displays and handles automatic resizing on overflow."""

    def __init__(self, font_size: int, guess_to_player: dict[str, int]) -> None:
        from src.config.display_constants import FONT_SIZE_DELTA
        self.font_size_delta = FONT_SIZE_DELTA
        self.guess_to_player = guess_to_player
        self.previous_guesses_display = PreviousGuessesDisplay(font_size, guess_to_player)
        self.remaining_previous_guesses_display = RemainingPreviousGuessesDisplay(
            font_size - self.font_size_delta, guess_to_player)

    def resize(self, now_ms: int) -> None:
        """Resize both displays to fit more words."""
        from typing import cast
        font_size = (cast(float, self.previous_guesses_display.font.size) * 4.0) / 5.0
        new_font_size = max(1, int(font_size))
        
        self.previous_guesses_display = PreviousGuessesDisplay.from_instance(
            self.previous_guesses_display, new_font_size, now_ms)
        self.remaining_previous_guesses_display = RemainingPreviousGuessesDisplay.from_instance(
            self.remaining_previous_guesses_display, int(new_font_size - self.font_size_delta))
        
        self.previous_guesses_display.draw()
        self.remaining_previous_guesses_display.draw()

    def exec_with_resize(self, f, now_ms: int):
        """Execute a function and resize displays if it triggers a TextRectException."""
        retry_count = 0
        while True:
            try:
                retry_count += 1
                if retry_count > 2:
                    raise Exception("too many TextRectException in PreviousGuessesManager")
                return f()
            except textrect.TextRectException:
                self.resize(now_ms)

    def add_guess(self, previous_guesses: list[str], guess: str, player: int, now_ms: int) -> None:
        """Add a new guess with automatic resizing."""
        self.exec_with_resize(lambda: self.previous_guesses_display.add_guess(
            previous_guesses, guess, player, now_ms), now_ms)

    def update_previous_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        """Update previous guesses with automatic resizing."""
        self.exec_with_resize(lambda: self.previous_guesses_display.update_previous_guesses(
            previous_guesses, now_ms), now_ms)

    def update_remaining_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        """Update remaining guesses with automatic resizing."""
        self.exec_with_resize(lambda: self.remaining_previous_guesses_display.update_remaining_guesses(
            previous_guesses), now_ms)

    def update(self, window: pygame.Surface, now_ms: int) -> None:
        """Update all displays with automatic resizing."""
        def update_all_displays():
            self.previous_guesses_display.update(window, now_ms)
            self.remaining_previous_guesses_display.update(
                window, self.previous_guesses_display.surface.get_bounding_rect().height)

        self.exec_with_resize(update_all_displays, now_ms)

    def old_guess(self, old_guess: str, now_ms: int) -> None:
        """Handle an old guess display."""
        self.previous_guesses_display.old_guess(old_guess, now_ms)
