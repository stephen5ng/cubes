"""Game state coordinator managing all game components."""

import logging
import pygame
import pygame.freetype
from typing import cast, Optional
import easing_functions
import aiomqtt
import json

from core import app
from core import tiles
from core import tiles
from config import game_config
from config.player_config import PlayerConfigManager
from hardware import cubes_to_game
import os
import subprocess
import traceback
import random
from utils.pygameasync import events

from game.components import Score, Shield, StarsDisplay, NullStarsDisplay
from game.letter import GuessType, Letter
from game.recorder import GameRecorder, NullRecorder
from game.descent_strategy import DescentStrategy
from input.input_devices import InputDevice, CubesInput
from rendering.animations import LetterSource, PositionTracker, LETTER_SOURCE_RECOVERY
from rendering.metrics import RackMetrics
from rendering.rack_display import RackDisplay
from rendering.melt_effect import MeltEffect
from rendering.balloon_effect import BalloonEffect
from systems.sound_manager import SoundManager
from ui.guess_display import PreviousGuessesManager, PreviousGuessesDisplay, RemainingPreviousGuessesDisplay
from ui.game_over_display import GameOverDisplay

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
                 descent_duration_s: int,
                 recorder: Optional[GameRecorder],
                 replay_mode: bool,
                 one_round: bool,
                 min_win_score: int,
                 stars: bool,
                 level: int = 0,
                 next_column_ms: int = None,
                 letter_linger_ms: int = 0) -> None:
        self._app = the_app
        self.game_logger = game_logger
        self.output_logger = output_logger
        self.descent_duration_s = descent_duration_s
        self.recorder = recorder if recorder else NullRecorder()
        self.replay_mode = replay_mode
        self.one_round = one_round
        if min_win_score < 0:
            raise ValueError(f"min_win_score must be non-negative, got {min_win_score}")
        self.min_win_score = min_win_score
        self.level = level
        self.next_column_ms = next_column_ms
        self.letter_linger_ms = letter_linger_ms
        self.show_level = level > 0 or stars # Only show level if level > 0 or stars enabled (game_on mode)
        self.level_fade_start_ms = -1
        self.level_fade_duration_ms = 1000
        self.level_fade_easing = easing_functions.CubicEaseInOut(start=255, end=0, duration=self.level_fade_duration_ms)

        # Required dependency injection - no defaults!
        self.sound_manager = sound_manager
        self.rack_metrics = rack_metrics
        self.player_config_manager = PlayerConfigManager(rack_metrics.letter_width)
        
        # Initial configs: P0 starts as Single Player (-1), P1 is configured as P1 (1)
        # but inactive until 2-player mode starts.
        configs = [
            self.player_config_manager.get_single_player_config(),
            self.player_config_manager.get_config(1)
        ]

        # Now create components that depend on injected dependencies
        self.scores = [
            Score(the_app, configs[player], self.rack_metrics, stars_enabled=stars) 
            for player in range(game_config.MAX_PLAYERS)
        ]
        if stars:
            self.stars_display = StarsDisplay(self.rack_metrics, min_win_score=self.min_win_score, sound_manager=self.sound_manager)
        else:
            self.stars_display = NullStarsDisplay()
        letter_y = self.scores[0].get_size()[1] + 4

        self.letter = Letter(letter_font, letter_y, self.rack_metrics, self.output_logger, letter_beeps, letter_strategy, level=level, next_column_ms=next_column_ms, letter_linger_ms=letter_linger_ms)
        self.racks = [
            RackDisplay(the_app, self.rack_metrics, self.letter, configs[player]) 
            for player in range(game_config.MAX_PLAYERS)
        ]
        self.guess_to_player = {}
        self.guesses_manager = PreviousGuessesManager(self.guess_to_player, self.player_config_manager)
        self.spawn_source = LetterSource(
            self.letter,
            self.rack_metrics.get_rect().x, self.rack_metrics.get_rect().width,
            letter_y)

        # Add recovery line that takes twice as long to fall
        self.recovery_tracker = PositionTracker(recovery_strategy)
        # Recovery line is hidden
        self.recovery_source = None
        
        self.game_over_display = GameOverDisplay()

        self.shields: list[Shield] = []
        self.running = False
        self.aborted = False
        self.input_devices = []
        self.last_lock = False

        # Initialize time tracking
        self.start_time_s = 0
        self.stop_time_s = 0
        self.last_letter_time_s = 0.0
        self.exit_code = 0

        # Melting effect state
        self.melt_effect: Optional[MeltEffect] = None
        self.balloon_effects: list[BalloonEffect] = []

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

    def toggle_player_count(self) -> None:
        """Toggle between 1 and 2 player modes and update configurations."""
        new_count = 1 if self._app.player_count == 2 else 2
        self._app.player_count = new_count
        
        # Update configs based on new count
        if new_count == 2:
            p0_config = self.player_config_manager.get_config(0)
            self.racks[0].player_config = p0_config
            self.scores[0].player_config = p0_config
        else:
            single_config = self.player_config_manager.get_single_player_config()
            self.racks[0].player_config = single_config
            self.scores[0].player_config = single_config
            
        # Redraw all components
        for player in range(game_config.MAX_PLAYERS):
            if player < len(self.scores):
                self.scores[player].start()  # Redraws with new config
            if player < len(self.racks):
                self.racks[player].draw()

    def _draw_all_players(self) -> None:
        """Draw scores and racks for all players."""
        for player in range(self._app.player_count):
            self.scores[player].draw()
            self.racks[player].draw()

    def _update_all_scores(self, window: pygame.Surface) -> None:
        """Update display for all player scores."""
        for player in range(self._app.player_count):
            self.scores[player].update(window)

    def _update_all_racks(self, window: pygame.Surface, now_ms: int) -> None:
        """Update display for all player racks."""
        for player in range(self._app.player_count):
            self.racks[player].update(window, now_ms)

    def _update_racks_preserving_running_state(self, window: pygame.Surface, now_ms: int) -> None:
        """Update racks while preserving their running state (used for game-over capture)."""
        for player in range(self._app.player_count):
            if hasattr(self.racks[player], 'surface') and self.racks[player].surface is not None:
                original_running = self.racks[player].running
                self.racks[player].running = True
                self.racks[player].update(window, now_ms, flash=False)
                self.racks[player].running = original_running

    async def update_rack(self, tiles: list[tiles.Tile], highlight_length: int, guess_length: int, player: int, now_ms: int, guessed_tile_ids: list[str] | None) -> None:
        """Update rack display for a player."""
        await self.racks[player].update_rack(tiles, highlight_length, guess_length, now_ms, guessed_tile_ids)

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
                print(f"starting second player with input_device: {input_device}, {self.input_devices}")
                # Maxed out player count
                if self._app.player_count >= 2:
                    return -1

                self._app.player_count = 2
                
                # Switch P0 to multiplayer configuration
                p0_config = self.player_config_manager.get_config(0)
                self.racks[0].player_config = p0_config
                self.scores[0].player_config = p0_config
                self.scores[0].start() # Re-draw with new config/position
                self.racks[0].draw()   # Re-draw rack
                self.input_devices.append(str(input_device))
                self._draw_all_players()
                # Load letters for both players when entering 2-player mode
                await self._app.load_rack(now_ms)
                return 1

        self._app.player_count = 1
        
        # Reset P0 to single player configuration
        single_config = self.player_config_manager.get_single_player_config()
        self.racks[0].player_config = single_config
        self.scores[0].player_config = single_config
        self.scores[0].start()
        self.racks[0].draw()

        print(f"{now_ms} starting new game with input_device: {input_device}")
        self.input_devices = [str(input_device)]
        print(f"ADDED {str(input_device)} in self.input_devices: {str(input_device) in self.input_devices}")

        self.guess_to_player = {}
        self.guesses_manager = PreviousGuessesManager(self.guess_to_player, self.player_config_manager)
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
        print(f"[DEBUG] stage_guess called with word='{last_guess}', player={player}")
        await self.sound_manager.queue_word_sound(last_guess, player)
        self.racks[player].guess_type = GuessType.GOOD
        self.shields.append(Shield(
            self.rack_metrics.get_rect().topleft, 
            last_guess, 
            score, 
            player,
            self.racks[player].player_config, 
            now_ms
        ))

    async def accept_letter(self, now_ms: int) -> None:
        """Accept the falling letter into the rack."""
        await self._app.accept_new_letter(self.letter.letter, self.letter.letter_index(), now_ms)
        self.letter.letter = ""
        self.last_letter_time_s = now_ms/1000

    async def stop(self, now_ms: int, exit_code: int) -> None:
        """Stop the game."""
        if not self.running:
            return

        # Calculate stars earned (accounts for baseline score)
        num_stars = self.stars_display.calculate_stars_for_score(self.scores[0].score)

        # When stars are enabled, player must earn 3 stars to win
        if self.min_win_score > 0 and num_stars >= 3:
            logger.info(f"Stars earned: {num_stars} >= 3. Setting exit code to 10 (Win)")
            exit_code = 10
        elif self.min_win_score > 0 and num_stars < 3:
            # Less than 3 stars with stars enabled = loss, regardless of score
            logger.info(f"Stars earned: {num_stars} < 3. Setting exit code to 11 (Loss)")
            exit_code = 11
        # Otherwise, keep the original exit_code (for games without stars enabled)

        self.exit_code = exit_code
        if exit_code != 10:
            self.sound_manager.play_sad_trombone()
        logger.info(f"GAME OVER (Exit Code: {exit_code})")
        for rack in self.racks:
            rack.stop()

        # Reset effects for next game
        self.melt_effect = None
        self.balloon_effects = []
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

        await self._app.stop(now_ms, self.min_win_score)

        # Publish final score to control broker
        await self._publish_final_score(exit_code, num_stars)

        logger.info("GAME OVER OVER")

    async def _publish_final_score(self, exit_code: int, num_stars: int) -> None:
        """Publish final game score to the control MQTT broker."""
        try:
            score_data = {
                "score": self.scores[0].score,
                "stars": num_stars,
                "exit_code": exit_code,
                "min_win_score": self.min_win_score,
                "duration_s": self.stop_time_s - self.start_time_s if self.stop_time_s else 0
            }

            async with aiomqtt.Client(
                hostname=game_config.MQTT_SERVER,
                port=game_config.MQTT_CLIENT_PORT
            ) as client:
                await client.publish(
                    "game/final_score",
                    json.dumps(score_data),
                    retain=True
                )
                logger.info(f"Published final score: {score_data}")
        except Exception as e:
            logger.error(f"Failed to publish final score to control broker: {e}")

    async def next_tile(self, next_letter: str, now_ms: int) -> None:
        """Update the next letter to fall."""
        if self.one_round or (self.letter.get_screen_bottom_y() + Letter.Y_INCREMENT*3 > self.rack_metrics.get_rect().y):
            next_letter = "!!!!!!"
        self.letter.change_letter(next_letter, now_ms)

    async def add_guess(self, previous_guesses: list[str], guess: str, player: int, now_ms: int) -> None:
        """Add a new guess to the display."""
        if not self.running:
            return
            
        if self.show_level and self.level_fade_start_ms == -1:
            self.level_fade_start_ms = now_ms

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
        now_s = now_ms / 1000.0
        if not self.running:
            time_since_over = now_s - self.stop_time_s
            # Only animate (rainbow) if it's a WIN (exit_code == 10)
            if self.exit_code == 10 and time_since_over < 15.0:
                game_over_animate = True

        # Only enable melting if racks have been properly initialized (surfaces exist)
        racks_initialized = all(hasattr(rack, 'surface') and rack.surface is not None for rack in self.racks)

        if not self.running and self.exit_code != 10 and racks_initialized:
             # Melting logic for "Game Lost"
             if self.melt_effect is None:
                  # First frame of loss: Capture the screen
                  # Note: 'window' might be black here since run_single_frame clears it.
                  # We should redraw everything one last time to capture the final state.
                  
                  # Re-draw the scene as if the game were running for one frame
                  window.fill((0, 0, 0))
                  self.guesses_manager.update(window, now_ms, game_over=game_over_animate)

                  # Force racks to draw their letters instead of "GAME OVER" text
                  self._update_racks_preserving_running_state(window, now_ms)

                  for shield in self.shields:
                      shield.update(window, now_ms)

                  # Capture the screen WITHOUT the score (score will be drawn on top and not melted)
                  self.melt_effect = MeltEffect(window)
             
             # Render Melt (on subsequent frames only)
             else:
                 window.fill((0, 0, 0))
                 self.melt_effect.update()
                 self.melt_effect.draw(window)

                 # Draw stars on top of the melt (so they don't melt)
                 self.stars_display.update(window, now_ms)

                 # Draw score on top of the melt (so it doesn't melt)
                 self._update_all_scores(window)

                 self.game_over_display.draw(window, won=False, now_ms=now_ms)

                 # Skip normal component updates
                 return incidents

        # Winning logic for "Game Won"
        if not self.running and self.exit_code == 10:
             if not self.balloon_effects:
                 # First frame of win: draw guesses to populate surfaces before
                 # reading their geometry for balloon placement
                 window.fill((0, 0, 0))
                 self.guesses_manager.update(window, now_ms, game_over=game_over_animate)

                 # Initialize BalloonEffects
                 config_manager = self.guesses_manager.config_manager
                 
                 # 1. Main previous guesses
                 pg_display = self.guesses_manager.previous_guesses_display
                 words_pg = pg_display.previous_guesses
                 if words_pg:
                     colors_pg = [config_manager.get_config(pg_display.guess_to_player.get(w, 0)).shield_color for w in words_pg]
                     renderer_pg = pg_display._text_rect_renderer
                     self.balloon_effects.append(
                         BalloonEffect(renderer_pg, words_pg, colors_pg, PreviousGuessesDisplay.POSITION_TOP, rainbow=True)
                     )

                 # 2. Remaining/Overflow guesses
                 rem_display = self.guesses_manager.remaining_previous_guesses_display
                 words_rem = rem_display.remaining_guesses
                 if words_rem:
                     colors_rem = [config_manager.get_config(rem_display.guess_to_player.get(w, 0)).shield_color for w in words_rem]
                     renderer_rem = rem_display._text_rect_renderer
                     
                     # Calculate offset: Top + Height of valid guesses + Gap
                     # Ensure surface of valid guesses is updated or at least has correct rect
                     height_pg = pg_display.surface.get_bounding_rect().height
                     start_y_rem = PreviousGuessesDisplay.POSITION_TOP + height_pg + RemainingPreviousGuessesDisplay.TOP_GAP
                     
                     self.balloon_effects.append(
                         BalloonEffect(renderer_rem, words_rem, colors_rem, start_y_rem, rainbow=True)
                     )

                 self.stars_display.start_post_game_spin()

             window.fill((0, 0, 0))
             
             for effect in self.balloon_effects:
                 effect.update()
                 effect.draw(window)
             
             self.stars_display.update(window, now_ms)
             self._update_all_scores(window)
             self.game_over_display.draw(window, won=True, now_ms=now_ms)

             return incidents

        # Normal Update Loop
        if self.show_level:
            alpha = 255
            if self.level_fade_start_ms > 0:
                elapsed = now_ms - self.level_fade_start_ms
                if elapsed >= self.level_fade_duration_ms:
                    self.show_level = False
                    alpha = 0
                else:
                    alpha = int(self.level_fade_easing(elapsed))
            
            if self.show_level:
                # Draw Level in the background
                level_color = game_config.REMAINING_PREVIOUS_GUESSES_COLOR
                self.game_over_display.draw_text(window, f"LEVEL\n{self.level}", level_color, alpha=alpha)
        
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

        self._update_all_racks(window, now_ms)
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
                num_stars = self.stars_display.draw(self.scores[0].score, now_ms)
                # Stars are just visual feedback during the game; winning status is evaluated at game end.
                
                self._app.add_guess(shield.letters, shield.player)
                self.sound_manager.play_crash()


        self.shields[:] = [s for s in self.shields if s.active]
        self._update_all_scores(window)
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
        
        if not self.running and self.exit_code == 10:
             self.game_over_display.draw(window, won=True, now_ms=now_ms)

        self.recorder.capture(window, now_ms)
        return incidents
