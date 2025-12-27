"""UI components for displaying game information."""

import pygame
import pygame.freetype
import sys
import os

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from blockwords.utils import textrect

# Constants from main game
SCREEN_WIDTH = 192
SCREEN_HEIGHT = 256
OLD_GUESS_COLOR = pygame.Color("yellow")
SHIELD_COLOR_P0 = pygame.Color("DarkOrange4") 
SHIELD_COLOR_P1 = pygame.Color("DarkSlateBlue")
FADER_COLOR_P0 = pygame.Color("orange")
FADER_COLOR_P1 = pygame.Color("lightblue")


class LastGuessFader:
    """Fades out the last guess display over time."""
    
    def __init__(self, text: str, starting_position: tuple[int, int], font: pygame.freetype.Font,
                 text_rect_renderer, start_time_ms: int, fade_duration_ms: int, color: pygame.Color) -> None:
        self.text = text
        self.start_position = starting_position
        self.font = font
        self.text_rect_renderer = text_rect_renderer
        self.start_time_ms = start_time_ms
        self.fade_duration_ms = fade_duration_ms
        self.color = color

    def is_active(self, now_ms: int) -> bool:
        """Check if the fader is still active."""
        return now_ms < self.start_time_ms + self.fade_duration_ms

    def get_fade_alpha(self, now_ms: int) -> float:
        """Get the current fade alpha value."""
        if not self.is_active(now_ms):
            return 0.0
        elapsed_ms = now_ms - self.start_time_ms
        return 1.0 - (elapsed_ms / self.fade_duration_ms)

    def render(self, surface: pygame.Surface, now_ms: int) -> None:
        """Render the fading text."""
        if not self.is_active(now_ms):
            return
        
        alpha = self.get_fade_alpha(now_ms)
        color_with_alpha = pygame.Color(self.color.r, self.color.g, self.color.b, int(255 * alpha))
        text_surface, _ = self.font.render(self.text, color_with_alpha)
        surface.blit(text_surface, self.start_position)


class FaderManager:
    """Manages multiple text faders."""
    
    def __init__(self, previous_guesses: list[str], font: pygame.freetype.Font, text_rect_renderer) -> None:
        self.previous_guesses = previous_guesses
        self.font = font
        self.text_rect_renderer = text_rect_renderer

    def create_fader(self, guess: str, start_time_ms: int, duration_ms: int, color: pygame.Color) -> LastGuessFader:
        """Create a new fader for the given guess."""
        # Calculate position based on guess location in previous_guesses
        position = (0, 0)  # This would need proper position calculation
        return LastGuessFader(guess, position, self.font, self.text_rect_renderer,
                             start_time_ms, duration_ms, color)


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
        self.bloop_sound.play()

    def new_guess(self, new_guess: str, player: int, now_ms: int) -> None:
        """Handle display of a new guess with fade effect."""
        fader_color = self.FADER_PLAYER_COLORS[player]
        self.fader_inputs.append(
            [new_guess, now_ms, fader_color, PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS])
        self._try_add_fader(new_guess,
                            fader_color,
                            PreviousGuessesDisplay.FADE_DURATION_NEW_GUESS,
                            now_ms)

    def update_previous_guesses(self, previous_guesses: list[str]) -> None:
        """Update the list of previous guesses."""
        self.previous_guesses = previous_guesses
        self.draw()

    def render_faders(self, window: pygame.Surface, now_ms: int) -> None:
        """Render all active faders."""
        active_faders = []
        for fader in self.faders:
            if fader.is_active(now_ms):
                fader.render(window, now_ms)
                active_faders.append(fader)
        self.faders = active_faders

    def get_surface(self) -> pygame.Surface:
        """Get the rendered surface."""
        return self.surface

    def get_position(self) -> tuple[int, int]:
        """Get the display position."""
        return 0, self.POSITION_TOP


class RemainingPreviousGuessesDisplay(PreviousGuessesDisplayBase):
    """Display for showing remaining/unused previous guesses."""
    
    PLAYER_COLORS = [pygame.Color(SHIELD_COLOR_P0.r, SHIELD_COLOR_P0.g, SHIELD_COLOR_P0.b, 192),
                     pygame.Color(SHIELD_COLOR_P1.r, SHIELD_COLOR_P1.g, SHIELD_COLOR_P1.b, 192)]  # Static array for player colors with 0.5 alpha
    
    def __init__(self, font_size: int, guess_to_player: dict[str, int]) -> None:
        super().__init__(font_size)
        self.remaining_previous_guesses = []
        self.guess_to_player = guess_to_player
        self.draw()

    @classmethod
    def from_instance(cls, instance: 'RemainingPreviousGuessesDisplay', font_size: int) -> 'RemainingPreviousGuessesDisplay':
        """Create a new instance from an existing one with a new font size."""
        new_instance = cls(font_size, instance.guess_to_player)
        new_instance.remaining_previous_guesses = instance.remaining_previous_guesses
        new_instance.draw()
        return new_instance

    def draw(self) -> None:
        """Draw the remaining previous guesses display."""
        self.surface = self._text_rect_renderer.render(
            self.remaining_previous_guesses,
            [self.PLAYER_COLORS[self.guess_to_player.get(guess, 0)] for guess in self.remaining_previous_guesses])

    def update_remaining_previous_guesses(self, remaining_previous_guesses: list[str]) -> None:
        """Update the list of remaining previous guesses."""
        self.remaining_previous_guesses = remaining_previous_guesses
        self.draw()

    def get_surface(self) -> pygame.Surface:
        """Get the rendered surface."""
        return self.surface

    def get_position(self) -> tuple[int, int]:
        """Get the display position."""
        return 0, 150  # Positioned below the main previous guesses display