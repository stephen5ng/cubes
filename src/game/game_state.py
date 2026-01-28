"""Game state coordinator managing all game components."""

import logging
import pygame
import pygame.freetype
from typing import cast, Optional
import easing_functions

from core import app
from core import tiles
from config import game_config
from hardware import cubes_to_game
import os
import subprocess
import traceback
from utils.pygameasync import events

from game.components import Score, Shield, StarsDisplay, NullStarsDisplay
from game.letter import GuessType, Letter
from game.recorder import GameRecorder, NullRecorder
from game.descent_strategy import DescentStrategy
from input.input_devices import InputDevice, CubesInput
from rendering.animations import LetterSource, PositionTracker, LETTER_SOURCE_RECOVERY
from rendering.metrics import RackMetrics
from rendering.rack_display import RackDisplay
from systems.sound_manager import SoundManager
from ui.guess_display import PreviousGuessesManager

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
                 letter_beeps: list,
                 letter_strategy: DescentStrategy,
                 recovery_strategy: DescentStrategy,
                 previous_guesses_font_size: int,
                 remaining_guesses_font_size_delta: int,
                 descent_duration_s: int = 0,
                 recorder: Optional[GameRecorder] = None,
                 replay_mode: bool = False,
                 one_round: bool = False,
                 min_win_score: int = 0,
                 stars: bool = False) -> None:
        self._app = the_app
        self.game_logger = game_logger
        self.output_logger = output_logger
        self.descent_duration_s = descent_duration_s
        self.recorder = recorder if recorder else NullRecorder()
        self.replay_mode = replay_mode
        self.recorder = recorder if recorder else NullRecorder()
        self.replay_mode = replay_mode
        self.one_round = one_round
        self.min_win_score = min_win_score

        # Required dependency injection - no defaults!
        self.sound_manager = sound_manager
        self.rack_metrics = rack_metrics

        # Now create components that depend on injected dependencies
        self.scores = [Score(the_app, player, self.rack_metrics) for player in range(game_config.MAX_PLAYERS)]
        if stars:
            self.stars_display = StarsDisplay(self.rack_metrics)
        else:
            self.stars_display = NullStarsDisplay()
        letter_y = self.scores[0].get_size()[1] + 4

        self.letter = Letter(letter_font, letter_y, self.rack_metrics, self.output_logger, letter_beeps, letter_strategy)
        self.racks = [RackDisplay(the_app, self.rack_metrics, self.letter, player) for player in range(game_config.MAX_PLAYERS)]
        self.previous_guesses_font_size = previous_guesses_font_size
        self.remaining_guesses_font_size_delta = remaining_guesses_font_size_delta
        self.guess_to_player = {}
        self.guesses_manager = PreviousGuessesManager(self.previous_guesses_font_size, self.guess_to_player, self.remaining_guesses_font_size_delta)
        self.spawn_source = LetterSource(
            self.letter,
            self.rack_metrics.get_rect().x, self.rack_metrics.get_rect().width,
            letter_y)

        # Add recovery line that takes twice as long to fall
        self.recovery_tracker = PositionTracker(recovery_strategy)
        # Recovery line is hidden
        self.recovery_source = None

        self.shields: list[Shield] = []
        self.running = False
        self.aborted = False
        self.input_devices = []
        self.last_lock = False

        # Initialize time tracking
        self.start_time_s = 0
        self.start_time_s = 0
        self.stop_time_s = 0
        self.exit_code = 0

        events.on("game.stage_guess")(self.stage_guess)
        events.on("game.old_guess")(self.old_guess)
        events.on("game.bad_guess")(self.bad_guess)
        events.on("game.next_tile")(self.next_tile)
        events.on("game.abort")(self.abort)
        events.on("game.start_player")(self.start_cubes_player)
        events.on("input.remaining_previous_guesses")(self.update_remaining_guesses)
        events.on("input.update_previous_guesses")(self.update_previous_guesses)
        events.on("input.add_guess")(self.add_guess)
        events.on("rack.update_rack")(self.update_rack)
        events.on("rack.update_letter")(self.update_letter)


    async def update_rack(self, tiles: list[tiles.Tile], highlight_length: int, guess_length: int, player: int, now_ms: int) -> None:
        """Update rack display for a player."""
        await self.racks[player].update_rack(tiles, highlight_length, guess_length, now_ms)

    async def update_letter(self, changed_tile: tiles.Tile, player: int, now_ms: int) -> None:
        """Update a single letter tile with animation."""
        await self.racks[player].update_letter(changed_tile, now_ms)

    async def old_guess(self, old_guess: str, player: int, now_ms: int) -> None:
        """Handle an old (duplicate) guess."""
        self.racks[player].guess_type = GuessType.OLD
        self.guesses_manager.old_guess(old_guess, now_ms)

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
                # Grace period to allow second player to join slightly after first player starts
                # This mirrors the ABC countdown window logic
                JOIN_GRACE_PERIOD_S = 6
                # Check if within grace period
                elapsed_s = (now_ms / 1000) - self.start_time_s
                if elapsed_s > JOIN_GRACE_PERIOD_S:
                    # Reject attempts to join after grace period
                    logging.info(f"Join rejected - game running for {elapsed_s:.1f}s (grace period {JOIN_GRACE_PERIOD_S}s). "
                                f"Input: {input_device}")
                    return -1

                # Add P2
                print(f"self.running: {self.running}, {str(input_device) in self.input_devices}, {self.input_devices}")
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
        self.guesses_manager = PreviousGuessesManager(self.previous_guesses_font_size, self.guess_to_player, self.remaining_guesses_font_size_delta)
        print(f"start_cubes: starting letter {now_ms}")
        self.letter.start(now_ms)
        if self.recovery_tracker:
            self.recovery_tracker.reset(now_ms)

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

    async def stop(self, now_ms: int, exit_code: int = 0) -> None:
        """Stop the game."""
        # Override exit code if score meets minimum win requirement
        if self.min_win_score > 0 and self.scores[0].score >= self.min_win_score:
            logger.info(f"Score {self.scores[0].score} >= min_win_score {self.min_win_score}. Setting exit code to 10 (Win)")
            exit_code = 10
            
        self.exit_code = exit_code
        self.sound_manager.play_game_over()
        logger.info(f"GAME OVER (Exit Code: {exit_code})")
        for rack in self.racks:
            rack.stop()
        self.input_devices = []
        self.running = False
        now_s = now_ms / 1000
        self.stop_time_s = now_s

        # Write duration log with context manager for safe file handling
        try:
            with open("output/durationlog.csv", "a") as duration_log:
                duration_log.write(f"{self.scores[0].score},{now_s-self.start_time_s}\n")
        except IOError as e:
            logger.error(f"Failed to write duration log: {e}")

        await self._app.stop(now_ms)
        logger.info("GAME OVER OVER")

    async def next_tile(self, next_letter: str, now_ms: int) -> None:
        """Update the next letter to fall."""
        if self.one_round or (self.letter.get_screen_bottom_y() + Letter.Y_INCREMENT*3 > self.rack_metrics.get_rect().y):
            next_letter = "!!!!!!"
        self.letter.change_letter(next_letter, now_ms)

    async def add_guess(self, previous_guesses: list[str], guess: str, player: int, now_ms: int) -> None:
        """Add a new guess to the display."""
        if not self.running:
            return
            
        self.guess_to_player[guess] = player
        self.guesses_manager.add_guess(previous_guesses, guess, player, now_ms)

    async def update_previous_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        """Update the previous guesses display."""
        self.guesses_manager.update_previous_guesses(previous_guesses, now_ms)

    async def update_remaining_guesses(self, previous_guesses: list[str], now_ms: int) -> None:
        """Update the remaining/unused guesses display."""
        self.guesses_manager.update_remaining_guesses(previous_guesses, now_ms)

    async def update(self, window: pygame.Surface, now_ms: int) -> None:
        """Update all game components and handle collisions."""
        incidents = []
        window.set_alpha(255)
        # Calculate if we should animate (Game Over and within 15s)
        game_over_animate = False
        if not self.running:
            time_since_over = (now_ms / 1000.0) - self.stop_time_s
            if time_since_over < 15.0:
                game_over_animate = True

        self.guesses_manager.update(window, now_ms, game_over=game_over_animate)

        self.guesses_manager.update(window, now_ms, game_over=game_over_animate)

        if self.running:

            # Update recovery line BEFORE spawn line so spawn draws on top
            if self.recovery_tracker:
                self.recovery_tracker.update(now_ms, self.letter.height)


            # Draw recovery gradient between spawn and recovery lines
            # Even if recovery line (source) is hidden, we show the gradient
            if self.spawn_source and self.recovery_tracker:
                y_recovery = self.spawn_source.initial_y + self.recovery_tracker.start_fall_y
                y_spawn = self.spawn_source.initial_y + self.letter.start_fall_y

                top = min(y_recovery, y_spawn)
                height = abs(y_recovery - y_spawn)

                if height > 0:
                    # Optimize: Use pre-calculated gradient source if possible, or create on the fly efficiently
                    # creating a 1x2 surface and scaling it is much faster than a loop
                    if not hasattr(self, '_gradient_source'):
                        # Create a high-fidelity gradient texture
                        texture_height = 256
                        self._gradient_source = pygame.Surface((1, texture_height), pygame.SRCALPHA)
                        
                        start_alpha = int(255 * 0.10)
                        end_alpha = int(255 * 0.80)
                        
                        # Use ExponentialEaseIn for the gradient curve
                        easing = easing_functions.ExponentialEaseIn(start=start_alpha, end=end_alpha, duration=texture_height)
                        
                        for y in range(texture_height):
                            alpha = int(easing(y))
                            # Clamp just in case
                            alpha = max(0, min(255, alpha))
                            self._gradient_source.set_at((0, y), (LETTER_SOURCE_RECOVERY.r, LETTER_SOURCE_RECOVERY.g, LETTER_SOURCE_RECOVERY.b, alpha))

                    # Smoothscale interpolates the colors/alpha between the two points
                    rect_surface = pygame.transform.smoothscale(self._gradient_source, (self.rack_metrics.get_rect().width, height))
                    window.blit(rect_surface, (self.rack_metrics.get_rect().x, top))

            if incident := self.spawn_source.update(window, now_ms):
                incidents.extend(incident)
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

                # Check if letter is at spawn line - if so, push both spawn line and letter up to recovery line
                letter_at_spawn_line = abs(self.letter.pos[1] - self.letter.start_fall_y) < 1  # Within n pixels tolerance
                if letter_at_spawn_line and self.recovery_tracker:
                    recovery_pos = self.recovery_tracker.start_fall_y
                    self.letter._apply_descent(recovery_pos, now_ms)
                    incidents.append("spawn_line_pushed_to_recovery")
                else:
                    # Normal bounce behavior
                    self.letter.shield_collision(now_ms)

                self.recorder.trigger(now_ms)

                self.scores[shield.player].update_score(shield.score)
                self.stars_display.draw(self.scores[0].score, now_ms)
                self._app.add_guess(shield.letters, shield.player)
                self.sound_manager.play_crash()


        self.shields[:] = [s for s in self.shields if s.active]
        for player in range(self._app.player_count):
            self.scores[player].update(window)
        self.stars_display.update(window, now_ms)

        # letter collide with rack
        if self.running and self.letter.get_screen_bottom_y() > self.rack_metrics.get_rect().y:
            incidents.append("letter_rack_collision")

            if self.letter.letter == "!!!!!!":
                await self.stop(now_ms, exit_code=11)
            else:
                self.sound_manager.play_chunk()
                self.letter.new_fall(now_ms)
                await self.accept_letter(now_ms)
        

        
        self.recorder.capture(window, now_ms)
        return incidents
