"""Rack display rendering and animation."""

import easing_functions
import pygame
from pygame import Color
import random

from core import app
from core import tiles
from config import game_config
from config.game_config import (
    SCREEN_WIDTH,
    BAD_GUESS_COLOR, GOOD_GUESS_COLOR, OLD_GUESS_COLOR,
    LETTER_SOURCE_COLOR, RACK_COLOR, FADER_COLOR_P0, FADER_COLOR_P1
)
from game.letter import GuessType, Letter
from rendering.animations import get_alpha
from rendering.metrics import RackMetrics


class RackDisplay:
    """Handles player's letter rack rendering and display."""

    LETTER_TRANSITION_DURATION_MS = 4000
    GUESS_TRANSITION_DURATION_MS = 800

    def __init__(self, the_app: app.App, rack_metrics: RackMetrics, falling_letter: Letter, player: int) -> None:
        self.the_app = the_app
        self.rack_metrics = rack_metrics
        self.player = player
        self.font = rack_metrics.font
        self.falling_letter = falling_letter
        self.tiles: list[tiles.Tile] = []
        self.running = False
        self.border = " "
        self.last_update_letter_ms = -RackDisplay.LETTER_TRANSITION_DURATION_MS
        self.easing = easing_functions.QuinticEaseInOut(start=0, end=255, duration=1)
        self.last_guess_ms = -RackDisplay.GUESS_TRANSITION_DURATION_MS
        self.highlight_length = 0
        self.select_count = 0
        self.cursor_position = 0
        self.transition_tile: tiles.Tile = None
        self.guess_type = GuessType.BAD
        self.guess_type_to_rect_color = {
            GuessType.BAD: BAD_GUESS_COLOR,
            GuessType.OLD: OLD_GUESS_COLOR,
            GuessType.GOOD: GOOD_GUESS_COLOR
            }
        self.game_over_surface, game_over_rect = self.font.render("GAME OVER", RACK_COLOR)
        self.game_over_pos = [SCREEN_WIDTH/2 - game_over_rect.width/2, rack_metrics.y]

        # Player -1 means single-player mode.
        self.left_offset_by_player = [0, -self.rack_metrics.letter_width*3, self.rack_metrics.letter_width*3]
        self.rack_color_by_player = [FADER_COLOR_P0, FADER_COLOR_P0, FADER_COLOR_P1]

    def _render_letter(self, surface: pygame.Surface,
        position: int, letter: str, color: pygame.Color) -> None:
        """Render a single letter at a position."""
        self.font.render_to(surface,
            self.rack_metrics.get_letter_rect(position, letter), letter, color)

    def letters(self) -> str:
        """Get the current letters in the rack as a string."""
        return ''.join([l.letter for l in self.tiles])

    def draw(self) -> None:
        """Draw the rack surface."""
        self.surface = pygame.Surface(self.rack_metrics.get_size())
        for ix, letter in enumerate(self.letters()):
            self._render_letter(self.surface, ix, letter, self.rack_color_by_player[self.player+1])

        pygame.draw.rect(self.surface,
            self.guess_type_to_rect_color[self.guess_type],
            self.rack_metrics.get_select_rect(self.select_count, self.player),
            1)

    def start(self) -> None:
        """Start the rack display."""
        self.running = True
        self.guess_type = GuessType.BAD
        self.draw()

    def stop(self) -> None:
        """Stop the rack display."""
        self.running = False
        self.draw()

    async def update_rack(self,
                          tiles: list[tiles.Tile],
                          highlight_length: int,
                          guess_length: int,
                          now_ms: int) -> None:
        """Update the rack with new tiles and highlight state."""
        self.tiles = tiles
        self.highlight_length = highlight_length
        self.last_guess_ms = now_ms
        self.select_count = guess_length
        self.draw()

    async def update_letter(self, tile: tiles.Tile, now_ms: int) -> None:
        """Update a single letter tile with animation."""
        self.last_update_letter_ms = now_ms
        self.transition_tile = tile
        self.draw()

    def _render_fading_letters(self, surface_with_faders: pygame.Surface, now: int) -> None:
        """Render fading letter transitions and good word highlights."""
        def make_color(color: pygame.Color, alpha: int) -> pygame.Color:
            new_color = Color(color)
            new_color.a = alpha
            return new_color

        new_letter_alpha = get_alpha(self.easing,
            self.last_update_letter_ms, RackDisplay.LETTER_TRANSITION_DURATION_MS, now)
        if new_letter_alpha and self.transition_tile in self.tiles:
            self._render_letter(
                surface_with_faders,
                self.tiles.index(self.transition_tile),
                self.transition_tile.letter,
                make_color(LETTER_SOURCE_COLOR, new_letter_alpha))

        good_word_alpha = get_alpha(self.easing, self.last_guess_ms, RackDisplay.GUESS_TRANSITION_DURATION_MS, now)
        if good_word_alpha:
            color = make_color(GOOD_GUESS_COLOR, good_word_alpha)
            letters = self.letters()
            for ix in range(0, self.highlight_length):
                self._render_letter(surface_with_faders, ix, letters[ix], color)

    def _render_flashing_letters(self, surface_with_faders: pygame.Surface) -> None:
        """Render flashing letters when falling letter is locked."""
        if self.falling_letter.locked_on and self.running:
            if random.randint(0, 2) == 0:
                if self.falling_letter.letter == "!!!!!!":
                    letter_index = random.randint(0, tiles.MAX_LETTERS - 1)
                else:
                    letter_index = self.falling_letter.letter_index()
                    if self.the_app.player_count > 1:
                        # Only flash letters in our half of the rack
                        hit_rack = 0 if letter_index < 3 else 1
                        if self.player != hit_rack:
                            return
                        letter_index += 3 * (1 if hit_rack == 0 else -1)
                surface_with_faders.fill(Color("black"),
                    rect=self.rack_metrics.get_largest_letter_rect(letter_index),
                    special_flags=pygame.BLEND_RGBA_MULT)

    def update(self, window: pygame.Surface, now: int) -> None:
        """Update and render the rack to the window."""
        if not self.running:
            window.blit(self.game_over_surface, self.game_over_pos)
            return
        surface = self.surface.copy()
        self._render_flashing_letters(surface)
        self._render_fading_letters(surface, now)
        top_left = self.rack_metrics.get_rect().topleft
        player_index = 0 if self.the_app.player_count == 1 else self.player+1
        top_left = (top_left[0] + self.left_offset_by_player[player_index], top_left[1])
        window.blit(surface, top_left)
