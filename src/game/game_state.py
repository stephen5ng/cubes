"""Game state coordinator managing all game components."""

import logging
import pygame
import pygame.freetype
from typing import cast

from blockwords.core import app
from blockwords.core import tiles
from blockwords.core.config import MAX_PLAYERS
from blockwords.utils.pygameasync import events
from blockwords.utils import textrect
from src.config.display_constants import FONT_SIZE_DELTA
from src.game.components import Score, Shield
from src.game.letter import GuessType, Letter
from src.input.input_devices import InputDevice, CubesInput
from src.rendering.animations import LetterSource
from src.rendering.metrics import RackMetrics
from src.rendering.rack_display import Rack
from src.systems.sound_manager import SoundManager
from src.ui.guess_display import PreviousGuessesDisplay, RemainingPreviousGuessesDisplay

logger = logging.getLogger(__name__)


class Game:
    """Coordinates all game components and manages game state."""

    def __init__(self,
                 the_app: app.App,
                 letter_font: pygame.freetype.Font,
                 game_logger,
                 output_logger,
                 sound_manager: SoundManager,
                 rack_metrics: RackMetrics,
                 letter_beeps: list) -> None:
        self._app = the_app
        self.game_logger = game_logger
        self.output_logger = output_logger

        # Required dependency injection - no defaults!
        self.sound_manager = sound_manager
        self.rack_metrics = rack_metrics

        # Now create components that depend on injected dependencies
        self.scores = [Score(the_app, player, self.rack_metrics) for player in range(MAX_PLAYERS)]
        letter_y = self.scores[0].get_size()[1] + 4
        self.letter = Letter(letter_font, letter_y, self.rack_metrics, self.output_logger, letter_beeps)
        self.racks = [Rack(the_app, self.rack_metrics, self.letter, player) for player in range(MAX_PLAYERS)]
        self.guess_to_player = {}
        self.previous_guesses_display = PreviousGuessesDisplay(PreviousGuessesDisplay.FONT_SIZE, self.guess_to_player)
        self.remaining_previous_guesses_display = RemainingPreviousGuessesDisplay(
            PreviousGuessesDisplay.FONT_SIZE - FONT_SIZE_DELTA, self.guess_to_player)
        self.letter_source = LetterSource(
            self.letter,
            self.rack_metrics.get_rect().x, self.rack_metrics.get_rect().width,
            letter_y)
        self.shields: list[Shield] = []
        self.running = False
        self.aborted = False
        self.game_log_f = open("output/gamelog.csv", "w")
        self.duration_log_f = open("output/durationlog.csv", "w")
        self.input_devices = []
        self.last_lock = False

        # TODO(sng): remove f
        events.on(f"game.stage_guess")(self.stage_guess)
        events.on(f"game.old_guess")(self.old_guess)
        events.on(f"game.bad_guess")(self.bad_guess)
        events.on(f"game.next_tile")(self.next_tile)
        events.on(f"game.abort")(self.abort)
        events.on(f"game.start_player")(self.start_cubes_player)
        events.on(f"input.remaining_previous_guesses")(self.update_remaining_guesses)
        events.on(f"input.update_previous_guesses")(self.update_previous_guesses)
        events.on(f"input.add_guess")(self.add_guess)
        events.on(f"rack.update_rack")(self.update_rack)
        events.on(f"rack.update_letter")(self.update_letter)

    async def update_rack(self, tiles: list[tiles.Tile], highlight_length: int, guess_length: int, player: int, now_ms: int) -> None:
        """Update rack display for a player."""
        await self.racks[player].update_rack(tiles, highlight_length, guess_length, now_ms)

    async def update_letter(self, changed_tile: tiles.Tile, player: int, now_ms: int) -> None:
        """Update a single letter tile with animation."""
        await self.racks[player].update_letter(changed_tile, now_ms)

    async def old_guess(self, old_guess: str, player: int, now_ms: int) -> None:
        """Handle an old (duplicate) guess."""
        self.racks[player].guess_type = GuessType.OLD
        self.previous_guesses_display.old_guess(old_guess, now_ms)

    async def bad_guess(self, player: int) -> None:
        """Handle a bad (invalid) guess."""
        self.racks[player].guess_type = GuessType.BAD

    async def abort(self) -> None:
        """Abort the current game."""
        self.aborted = True

    async def start_cubes(self, now_ms: int) -> None:
        """Start game from cubes input."""
        await self.start(CubesInput(None), now_ms)

    async def start_cubes_player(self, now_ms: int, player: int) -> None:
        """Start game for a specific player."""
        # Create player-specific CubesInput to enable proper 2-player mode
        cubes_input = CubesInput(None)
        cubes_input.id = f"player_{player}"
        print(f"Starting cubes for player {player} with input device: {cubes_input.id}")
        await self.start(cubes_input, now_ms)

    async def start(self, input_device: InputDevice, now_ms: int) -> None:
        """Start a new game or add a second player."""
        if self.running:
            if str(input_device) not in self.input_devices:
                # Add P2
                print(f"self.running: {self.running}, {str(input_device) in self.input_devices}, {self.input_devices}")
                print(f"starting second player with input_device: {input_device}, {self.input_devices}")
                # Maxed out player count
                if self._app.player_count >= 2:
                    return -1

                self._app.player_count = 2
                self.input_devices.append(str(input_device))
                for player in range(2):
                    self.scores[player].draw()
                    self.racks[player].draw()
                # Load letters for both players when entering 2-player mode
                await self._app.load_rack(now_ms)
                return 1

        self._app.player_count = 1
        print(f"{now_ms} starting new game with input_device: {input_device}")
        self.input_devices = [str(input_device)]
        print(f"ADDED {str(input_device)} in self.input_devices: {str(input_device) in self.input_devices}")
        self.guess_to_player = {}
        self.previous_guesses_display = PreviousGuessesDisplay(PreviousGuessesDisplay.FONT_SIZE, self.guess_to_player)
        self.remaining_previous_guesses_display = RemainingPreviousGuessesDisplay(
            PreviousGuessesDisplay.FONT_SIZE - FONT_SIZE_DELTA, self.guess_to_player)
        print(f"start_cubes: starting letter {now_ms}")
        self.letter.start(now_ms)
        for score in self.scores:
            score.start()
        for rack in self.racks:
            rack.start()
        self.running = True
        now_s = now_ms / 1000
        self.stop_time_s = -1000
        self.last_letter_time_s = now_s
        self.start_time_s = now_s
        await self._app.start(now_ms)
        self.sound_manager.play_start()
        print("start done")
        return 0

    async def stage_guess(self, score: int, last_guess: str, player: int, now_ms: int) -> None:
        """Stage a good guess with shield animation."""
        await self.sound_manager.queue_word_sound(last_guess, player)
        self.racks[player].guess_type = GuessType.GOOD
        self.shields.append(Shield(self.rack_metrics.get_rect().topleft, last_guess, score, player, now_ms))

    async def accept_letter(self, now_ms: int) -> None:
        """Accept the falling letter into the rack."""
        await self._app.accept_new_letter(self.letter.letter, self.letter.letter_index(), now_ms)
        self.letter.letter = ""
        self.last_letter_time_s = now_ms/1000

    async def stop(self, now_ms: int) -> None:
        """Stop the game."""
        self.sound_manager.play_game_over()
        logger.info("GAME OVER")
        for rack in self.racks:
            rack.stop()
        self.input_devices = []
        self.running = False
        now_s = now_ms / 1000
        self.stop_time_s = now_s
        self.duration_log_f.write(
            f"{self.scores[0].score},{now_s-self.start_time_s}\n")
        self.duration_log_f.flush()
        await self._app.stop(now_ms)
        logger.info("GAME OVER OVER")

    async def next_tile(self, next_letter: str, now_ms: int) -> None:
        """Update the next letter to fall."""
        if self.letter.get_screen_bottom_y() + Letter.Y_INCREMENT*3 > self.rack_metrics.get_rect().y:
            next_letter = "!"
        self.letter.change_letter(next_letter, now_ms)

    def resize_previous_guesses(self, now_ms: int) -> None:
        """Resize previous guesses display to fit more words."""
        font_size = (cast(float, self.previous_guesses_display.font.size)*4.0)/5.0
        self.previous_guesses_display = PreviousGuessesDisplay.from_instance(
            self.previous_guesses_display, max(1, int(font_size)), now_ms)
        self.remaining_previous_guesses_display = RemainingPreviousGuessesDisplay.from_instance(
            self.remaining_previous_guesses_display, int(font_size - FONT_SIZE_DELTA))
        self.previous_guesses_display.draw()
        self.remaining_previous_guesses_display.draw()

    def exec_with_resize(self, f, now_ms: int):
        """Execute function with automatic display resizing on overflow."""
        retry_count = 0
        while True:
            try:
                retry_count += 1
                if retry_count > 2:
                    raise Exception("too many TextRectException")
                return f()
            except textrect.TextRectException as e:
                # print(f"resize_previous_guesses: {e}")
                self.resize_previous_guesses(now_ms)

    async def add_guess(self, previous_guesses: list[str], guess: str, player: int, now_ms: int) -> None:
        """Add a new guess to the display."""
        self.guess_to_player[guess] = player
        self.exec_with_resize(lambda: self.previous_guesses_display.add_guess(
            previous_guesses, guess, player, now_ms),
                              now_ms)

    async def update_previous_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        """Update the previous guesses display."""
        self.exec_with_resize(
            lambda: self.previous_guesses_display.update_previous_guesses(
                previous_guesses, now_ms),
            now_ms)

    async def update_remaining_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        """Update the remaining/unused guesses display."""
        self.exec_with_resize(
            lambda: self.remaining_previous_guesses_display.update_remaining_guesses(previous_guesses),
            now_ms)

    def update_previous_guesses_with_resizing(self, window: pygame.Surface, now_ms: int) -> None:
        """Update all previous guess displays with automatic resizing."""
        def update_all_previous_guesses(self, window: pygame.Surface) -> None:
            self.previous_guesses_display.update(window, now_ms)
            self.remaining_previous_guesses_display.update(
                window, self.previous_guesses_display.surface.get_bounding_rect().height)

        self.exec_with_resize(lambda: update_all_previous_guesses(self, window),
                              now_ms)

    async def update(self, window: pygame.Surface, now_ms: int) -> None:
        """Update all game components and handle collisions."""
        incidents = []
        window.set_alpha(255)
        self.update_previous_guesses_with_resizing(window, now_ms)
        if incident := self.letter_source.update(window, now_ms):
            incidents.extend(incident)

        if self.running:
            if incident := self.letter.update(window, now_ms):
                incidents.extend(incident)

            if self.letter.locked_on or self.last_lock:
                self.last_lock = self.letter.locked_on
                if await self._app.letter_lock(self.letter.letter_index(), self.letter.locked_on, now_ms):
                    incidents.append("letter_lock")

        for player in range(self._app.player_count):
            self.racks[player].update(window, now_ms)
        for shield in self.shields:
            shield.update(window, now_ms)
            if shield.rect.y <= self.letter.get_screen_bottom_y():
                incidents.append("shield_letter_collision")
                shield.letter_collision()
                self.letter.shield_collision(now_ms)
                self.scores[shield.player].update_score(shield.score)
                self._app.add_guess(shield.letters, shield.player)
                self.sound_manager.play_crash()

        self.shields[:] = [s for s in self.shields if s.active]
        for player in range(self._app.player_count):
            self.scores[player].update(window)

        # letter collide with rack
        if self.running and self.letter.get_screen_bottom_y() > self.rack_metrics.get_rect().y:
            incidents.append("letter_rack_collision")
            if self.letter.letter == "!":
                await self.stop(now_ms)
            else:
                self.sound_manager.play_chunk()
                self.letter.new_fall(now_ms)
                await self.accept_letter(now_ms)
        return incidents
