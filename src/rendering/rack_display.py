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
    LETTER_SOURCE_COLOR, RACK_COLOR
)
from config.player_config import PlayerConfig
from game.letter import GuessType, Letter
from rendering.animations import get_alpha
from rendering.metrics import RackMetrics


class RackDisplay:
    """Handles player's letter rack rendering and display."""

    LETTER_TRANSITION_DURATION_MS = 4000
    GUESS_TRANSITION_DURATION_MS = 800

    def __init__(self, the_app: app.App, rack_metrics: RackMetrics, falling_letter: Letter, player_config: PlayerConfig) -> None:
        self.the_app = the_app
        self.rack_metrics = rack_metrics
        self.player_config = player_config
        self.player = player_config.player_id
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
        # Track multiple word highlights: list of (tile_ids, guess_type, timestamp_ms)
        # tile_ids is a list of tile IDs that form the highlighted word
        #
        # DESIGN: Multiple highlights allow showing feedback for multiple concurrent cube chains.
        # For example, if user forms "CAT" with cubes 1-2-3 and "DOG" with cubes 4-5-6,
        # both get persistent colored borders that remain until those chains are disconnected.
        #
        # PERSISTENCE: Highlights do NOT expire - they persist until:
        # 1. The specific chain is physically disconnected (targeted removal)
        # 2. The word is extended (e.g., "OV" → "OVL" removes the "OV" highlight)
        # 3. The game mode ends (all highlights cleared)
        self.highlights: list[tuple[list[str], GuessType, int]] = []
        # Track the last guess we added to avoid duplicates from repeated update_rack calls
        self._last_added_guess: tuple[list[str], GuessType, int] = None
        self.game_over_surface, game_over_rect = self.font.render("GAME OVER", RACK_COLOR)
        self.game_over_pos = [SCREEN_WIDTH/2 - game_over_rect.width/2, rack_metrics.y]

        self.game_over_pos = [SCREEN_WIDTH/2 - game_over_rect.width/2, rack_metrics.y]

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
            self._render_letter(self.surface, ix, letter, self.player_config.fader_color)

    def start(self) -> None:
        """Start the rack display."""
        self.running = True
        self.guess_type = GuessType.BAD
        self.highlights = []
        self.draw()

    def stop(self) -> None:
        """Stop the rack display."""
        self.running = False
        self.highlights = []
        self.draw()

    async def update_rack(self,
                          tiles: list[tiles.Tile],
                          highlight_length: int,
                          guess_length: int,
                          now_ms: int,
                          guessed_tile_ids: list[str] | None) -> None:
        """Update the rack with new tiles and highlight state."""
        self.tiles = tiles
        self.highlight_length = highlight_length
        self.last_guess_ms = now_ms
        self.select_count = guess_length

        # If guess_length is 0 but we have tile IDs, it's a removal request
        # (specific chain was disconnected - remove only that highlight)
        #
        # REMOVAL LOGIC: Use set.isdisjoint() to check if highlight should be removed.
        # A highlight is removed if it shares ANY tile IDs with the disconnected chain.
        # This handles:
        # - Exact matches: highlight ['1','2','3'] removed when ['1','2','3'] disconnected
        # - Word extensions: highlight ['1','2'] removed when ['1','2','3'] is formed (overlap)
        # - Preserves other highlights: ['4','5','6'] kept when ['1','2','3'] disconnected
        if guess_length == 0 and guessed_tile_ids:
            tile_id_set = set(guessed_tile_ids)
            original_count = len(self.highlights)
            # Remove any highlights that contain these tile IDs
            self.highlights = [
                (ids, gt, ts) for ids, gt, ts in self.highlights
                if tile_id_set.isdisjoint(set(ids))
            ]
            if len(self.highlights) != original_count:
                self._last_added_guess = None
            self.draw()
            return

        # Add this highlight to the list based on which tiles were guessed
        if guess_length > 0 and guessed_tile_ids:
            # Find positions of the guessed tiles in the current rack
            positions = []
            for tile_id in guessed_tile_ids:
                for pos, tile in enumerate(tiles):
                    if tile.id == tile_id:
                        positions.append(pos)
                        break

            if positions:
                # Sort positions and create highlight range
                positions.sort()
                start_pos = positions[0]
                end_pos = positions[-1]

                # Sort guessed_tile_ids for consistent comparison
                sorted_tile_ids = tuple(sorted(guessed_tile_ids))

                # Remove any existing highlights that overlap with this new one
                # This handles the case where a word is extended (e.g., "OV" -> "OVL")
                # Overlap means sharing any tile IDs
                original_count = len(self.highlights)
                new_tile_id_set = set(sorted_tile_ids)
                self.highlights = [(tile_ids, gt, ts) for tile_ids, gt, ts in self.highlights
                                  if new_tile_id_set.isdisjoint(set(tile_ids))]

                # Check if this is the same guess as the last one we added (avoid duplicates)
                new_guess = (list(sorted_tile_ids), self.guess_type, now_ms)
                if (self._last_added_guess and
                    self._last_added_guess[0] == list(sorted_tile_ids) and
                    self._last_added_guess[1] == self.guess_type and
                    now_ms - self._last_added_guess[2] < 100):  # Same guess within 100ms
                    return  # Skip adding this highlight

                # Add the new highlight
                self.highlights.append(new_guess)
                self._last_added_guess = new_guess

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
                    letter_index = self.player_config.get_flashing_index(
                        self.falling_letter.letter_index(),
                        self.the_app.player_count > 1
                    )
                    if letter_index is None:
                        return
                surface_with_faders.fill(Color("black"),
                    rect=self.rack_metrics.get_largest_letter_rect(letter_index),
                    special_flags=pygame.BLEND_RGBA_MULT)

    def update(self, window: pygame.Surface, now: int, flash: bool = True) -> None:
        """Update and render the rack to the window."""
        if not self.running:
            window.blit(self.game_over_surface, self.game_over_pos)
            return
        surface = self.surface.copy()
        if flash:
            self._render_flashing_letters(surface)
        self._render_fading_letters(surface, now)

        # Draw borders for all active highlights
        # Build a map of tile ID to position for quick lookup
        tile_id_to_pos = {tile.id: pos for pos, tile in enumerate(self.tiles)}

        for tile_ids, guess_type, timestamp_ms in self.highlights:
            # Find current positions of the tiles in this highlight
            positions = []
            for tile_id in tile_ids:
                if tile_id in tile_id_to_pos:
                    positions.append(tile_id_to_pos[tile_id])
                else:
                    # Tile no longer in rack (e.g., used in a word)
                    positions = None
                    break

            if not positions:
                # Skip drawing if tiles are gone
                continue

            # Check if tiles are still contiguous
            positions.sort()
            start_pos = positions[0]
            end_pos = positions[-1]
            expected_positions = list(range(start_pos, end_pos + 1))
            if positions != expected_positions:
                # Tiles are no longer contiguous (user separated them)
                continue

            # Build rect for this highlight range
            length = end_pos - start_pos + 1
            rect_width = self.rack_metrics.letter_width * length
            rect_x = self.rack_metrics.letter_width * start_pos
            rect = pygame.Rect(rect_x, 0, rect_width, self.rack_metrics.letter_height)

            color = self.guess_type_to_rect_color[guess_type]
            # Draw solid border (no expiration)
            pygame.draw.rect(surface, color, rect, 1)

        top_left = self.rack_metrics.get_rect().topleft
        top_left = (top_left[0] + self.player_config.rack_horizontal_offset, top_left[1])
        window.blit(surface, top_left)
