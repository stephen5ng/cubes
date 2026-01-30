"""Display components for showing previous guesses."""

import pygame
import pygame.freetype

from rendering import text_renderer as textrect
from config import game_config
from config.game_config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    SCREEN_WIDTH, SCREEN_HEIGHT,
    OLD_GUESS_COLOR, REMAINING_PREVIOUS_GUESSES_COLOR
)
from config.player_config import PlayerConfigManager
from ui.guess_faders import FaderManager, LastGuessFader
import logging

logger = logging.getLogger(__name__)


class PreviousGuessesDisplayBase:
    """Base class for displaying previous guesses."""

    FONT = "Arial"

    def __init__(self, font_size: int) -> None:
        if font_size <= 0:
            raise ValueError("Invalid font size")
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

    def __init__(self, font_size: int, guess_to_player: dict[str, int], config_manager: PlayerConfigManager) -> None:
        super().__init__(font_size)
        self.config_manager = config_manager
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
        new_instance = cls(font_size, instance.guess_to_player, instance.config_manager)
        new_instance.previous_guesses = instance.previous_guesses
        new_instance.fader_inputs = instance.fader_inputs
        new_instance.bloop_sound = instance.bloop_sound
        if instance.previous_guesses and instance.fader_inputs:
            new_instance._recreate_faders(now_ms)
        # Copy animation state
        new_instance._text_rect_renderer.animation_time = instance._text_rect_renderer.animation_time
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

    def draw(self, animate: bool = False) -> None:
        """Draw the previous guesses display."""
        colors = []
        for guess in self.previous_guesses:
            player_id = self.guess_to_player.get(guess, 0)
            colors.append(self.config_manager.get_config(player_id).shield_color)

        self.surface = self._text_rect_renderer.render(
            self.previous_guesses,
            colors,
            animate=animate)

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
        fader_color = self.config_manager.get_config(player).fader_color
        self.fader_inputs.append(
            [guess, now_ms, fader_color, PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS])
        self.update_previous_guesses(previous_guesses, now_ms)
        self._try_add_fader(guess,
                            fader_color,
                            PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS,
                            now_ms)

    def new_guess(self, new_guess: str, player: int, now_ms: int) -> None:
        """Handle display of a new guess with fade effect."""
        fader_color = self.config_manager.get_config(player).fader_color
        self.fader_inputs.append(
            [new_guess, now_ms, fader_color, PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS])
        self._try_add_fader(new_guess,
                            fader_color,
                            PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS,
                            now_ms)

    def update_previous_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        """Update the list of previous guesses and refresh faders."""
        # Try updating positions first - this will raise TextRectException if it overflows
        self._text_rect_renderer.update_pos_dict(previous_guesses)
        
        self.previous_guesses = previous_guesses
        self.fader_manager = FaderManager(self.previous_guesses, self.font, self._text_rect_renderer)
        self._recreate_faders(now_ms)
        self.draw()

    def update(self, window: pygame.Surface, now: int, game_over: bool = False) -> None:
        """Render the display with faders to the window."""
        # Drive animation (rainbow) only if game_over
        if self.previous_guesses and game_over:
            self.draw(animate=True)

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

    def __init__(self, font_size: int, guess_to_player: dict[str, int], config_manager: PlayerConfigManager) -> None:
        super().__init__(font_size)
        self.config_manager = config_manager
        self.guess_to_player = guess_to_player
        self.color = REMAINING_PREVIOUS_GUESSES_COLOR
        self.surface = pygame.Surface((0, 0))
        self.remaining_guesses = []

    @classmethod
    def from_instance(cls, instance: 'RemainingPreviousGuessesDisplay', font_size: int) -> 'RemainingPreviousGuessesDisplay':
        """Create a new instance from an existing one with a new font size."""
        new_instance = cls(font_size, instance.guess_to_player, instance.config_manager)
        new_instance.remaining_guesses = instance.remaining_guesses
        # Copy animation state
        new_instance._text_rect_renderer.animation_time = instance._text_rect_renderer.animation_time
        return new_instance

    def update(self, window: pygame.Surface, height: int, game_over: bool = False) -> None:
        """Render the display to the window at the appropriate position."""
        top = height + PreviousGuessesDisplay.POSITION_TOP + RemainingPreviousGuessesDisplay.TOP_GAP
        total_height = top + self.surface.get_bounding_rect().height
        if total_height > SCREEN_HEIGHT:
            if not game_over:
                raise textrect.TextRectException("can't update RemainingPreviousGuessesDisplay")
            return
            
        # Drive animation (rainbow) only if game_over
        if self.remaining_guesses and game_over:
            self.draw(animate=True)
            
        window.blit(self.surface, [0, top])

    def update_remaining_guesses(self, remaining_guesses: list[str]) -> None:
        """Update the list of remaining previous guesses."""
        self.remaining_guesses = remaining_guesses
        self.draw()

    def draw(self, animate: bool = False) -> None:
        """Draw the remaining previous guesses display."""
        colors = []
        for guess in self.remaining_guesses:
            player_id = self.guess_to_player.get(guess, 0)
            base_color = self.config_manager.get_config(player_id).shield_color
            colors.append(pygame.Color(base_color.r, base_color.g, base_color.b, 192))

        self.surface = self._text_rect_renderer.render(
            self.remaining_guesses,
            colors,
            animate=animate)


class PreviousGuessesManager:
    """Manages previous guess displays and handles automatic resizing on overflow."""

    DEFAULT_FONT_SIZE = 30

    def __init__(self, guess_to_player: dict[str, int], config_manager: PlayerConfigManager) -> None:
        self.font_size_delta = game_config.FONT_SIZE_DELTA
        self.guess_to_player = guess_to_player
        self.config_manager = config_manager
        self.previous_guesses_display = PreviousGuessesDisplay(self.DEFAULT_FONT_SIZE, guess_to_player, config_manager)
        self.remaining_previous_guesses_display = RemainingPreviousGuessesDisplay(
            self.DEFAULT_FONT_SIZE - self.font_size_delta, guess_to_player, config_manager)

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
                return f()
            except textrect.TextRectException:
                retry_count += 1
                if retry_count > 5:
                    logger.error("Unable to fit guesses even after resizing. Ignoring update.")
                    return
                self.resize(now_ms)

    def add_guess(self, previous_guesses: list[str], guess: str, player: int, now_ms: int) -> None:
        """Add a new guess."""
        self.exec_with_resize(lambda: self.previous_guesses_display.add_guess(previous_guesses, guess, player, now_ms), now_ms)

    def update_previous_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        """Update previous guesses."""
        self.exec_with_resize(lambda: self.previous_guesses_display.update_previous_guesses(previous_guesses, now_ms), now_ms)

    def update_remaining_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        """Update remaining guesses."""
        self.exec_with_resize(lambda: self.remaining_previous_guesses_display.update_remaining_guesses(previous_guesses), now_ms)

    def update(self, window: pygame.Surface, now_ms: int, game_over: bool = False) -> None:
        """Update all displays."""
        def _update():
            self.previous_guesses_display.update(window, now_ms, game_over=game_over)
            self.remaining_previous_guesses_display.update(
                window, self.previous_guesses_display.surface.get_bounding_rect().height, game_over=game_over)

        self.exec_with_resize(_update, now_ms)

    @property
    def is_full(self) -> bool:
        """Check if the display is effectively full (no room for another line)."""
        if not self.previous_guesses_display.previous_guesses:
            return False
            
        rect_prev = self.previous_guesses_display.surface.get_bounding_rect()
        height_prev = rect_prev.height
        
        # Calculate total bottom including remaining guesses if any
        total_bottom = PreviousGuessesDisplay.POSITION_TOP + height_prev
        
        if self.remaining_previous_guesses_display.remaining_guesses:
            rect_rem = self.remaining_previous_guesses_display.surface.get_bounding_rect()
            height_rem = rect_rem.height
            total_bottom += RemainingPreviousGuessesDisplay.TOP_GAP + height_rem
            
        available = SCREEN_HEIGHT - total_bottom
        line_height = self.previous_guesses_display.font.get_sized_height()
        
        # If available space is less than a line height, we are full.
        return available < line_height

    def old_guess(self, old_guess: str, now_ms: int) -> None:
        """Handle an old guess display."""
        self.previous_guesses_display.old_guess(old_guess, now_ms)
