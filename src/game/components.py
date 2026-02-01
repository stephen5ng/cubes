"""Game components for score and shield display."""

import math
import pygame
import pygame.freetype
import easing_functions

from core import app
from config import game_config
from config.game_config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FONT,
    SCORE_COLOR,
    TICKS_PER_SECOND,
    SHIELD_ACCELERATION_RATE,
    SHIELD_INITIAL_SPEED_MULTIPLIER,
    STAR_COLOR,
    EMPTY_STAR_COLOR
)
from config.player_config import PlayerConfig


class Score:
    """Displays and manages player score."""
    
    def __init__(self, the_app: app.App, player_config: PlayerConfig, rack_metrics, stars_enabled: bool) -> None:
        self.the_app = the_app
        self.player_config = player_config
        self.stars_enabled = stars_enabled
        
        # Required dependency injection - no fallback!
        font_size = rack_metrics.LETTER_SIZE
        self.star_height = 0
        if self.stars_enabled:
             font_size = int(font_size * 0.8)
             self.star_height = int(rack_metrics.LETTER_SIZE * 0.7 * 1.2)
             
        self.font = pygame.freetype.SysFont(FONT, font_size)
        self.pos = [0, 0]
        self.x = SCREEN_WIDTH/3 * (player_config.player_id+1)
        self.midscreen = SCREEN_WIDTH/2
        self.start()
        self.draw()

    def get_size(self) -> tuple[int, int]:
        """Get the size of the score display."""
        return self.surface.get_size()

    def start(self) -> None:
        """Initialize/reset the score."""
        self.score = 0
        self.draw()

    def draw(self) -> None:
        """Render the score text."""
        self.surface = self.font.render(str(self.score), SCORE_COLOR)[0]
        
        if self.player_config.player_id == -1:
            if self.stars_enabled:
                 # Right aligned (where stars were default)
                 self.pos[0] = int(SCREEN_WIDTH - self.surface.get_width() - 10)
                 # Adjust vertical position to align with stars
                 self.pos[1] = (self.star_height - self.surface.get_height()) // 2
            else:
                 # Center
                 self.pos[0] = int(self.midscreen - self.surface.get_width()/2)
                 self.pos[1] = 0
        else:
             self.pos[0] = int(self.x - self.surface.get_width()/2)
             self.pos[1] = 0

    def update_score(self, score: int) -> None:
        """Add points to the score."""
        self.score += score
        self.draw()

    def update(self, window: pygame.Surface) -> None:
        """Render the score to the window."""
        window.blit(self.surface, self.pos)


class Shield:
    """Flying text shield that shows scored words."""
    
    def __init__(self, base_pos: tuple[int, int], letters: str, score: int, player: int, player_config: PlayerConfig, now_ms: int) -> None:
        self.font = pygame.freetype.SysFont("Arial", int(2+math.log(1+score)*8))
        self.letters = letters
        self.base_pos = [base_pos[0], float(base_pos[1])]
        self.base_pos[1] -= self.font.get_rect("A").height
        self.pos = [self.base_pos[0], self.base_pos[1]]
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.score = score
        self.active = True
        self.player = player
        self.start_time_ms = now_ms
        self.initial_speed = -math.log(1+score) * SHIELD_INITIAL_SPEED_MULTIPLIER
        self.acceleration_rate = SHIELD_ACCELERATION_RATE
        self.surface = self.font.render(self.letters, player_config.fader_color)[0]
        self.pos[0] = int(SCREEN_WIDTH/2 - self.surface.get_width()/2)

    def update(self, window: pygame.Surface, now_ms: int) -> None:
        """Update and render the shield animation."""
        if self.active:
            update_count = (now_ms - self.start_time_ms) / (1000.0/TICKS_PER_SECOND)

            # Calculate position by summing up all previous speed contributions
            # This is a geometric series: initial_speed * (1 - (1.05)^update_count) / (1 - 1.05)
            displacement = self.initial_speed * (1 - (self.acceleration_rate ** update_count)) / (1 - self.acceleration_rate)
            self.pos[1] = self.base_pos[1] + displacement
            if window is not None:
                window.blit(self.surface, self.pos)

            # Get the tightest rectangle around the content for collision detection.
            self.rect = self.surface.get_bounding_rect().move(self.pos[0], self.pos[1])

    def letter_collision(self) -> None:
        """Handle collision with falling letter."""
        self.active = False
        self.pos[1] = SCREEN_HEIGHT


class StarsDisplay:
    """Displays stars in the upper right hand corner."""

    # Star earning animation timing
    STAR_SPIN_DURATION_MS = 800

    # Tada celebration blink animation timing
    BLINK_DURATION_PER_STAR_MS = 300  # Each star blinks for 300ms (increased from 200ms)
    BLINK_FADE_OUT_MS = 75  # Fade to 30% opacity in 75ms (increased from 50ms)
    BLINK_MIN_OPACITY = 0.3
    BLINK_STAR_OFFSET_MS = 150  # Stagger each star's blink by 150ms (increased from 100ms)
    TADA_TOTAL_DURATION_MS = 1500  # Total tada animation is 1500ms (increased from 1000ms)

    def __init__(self, rack_metrics, min_win_score: int, sound_manager) -> None:
        self.sound_manager = sound_manager
        self.min_win_score = min_win_score
        self.size = rack_metrics.LETTER_SIZE * 0.7
        self._filled_star = self._create_star_surface(self.size, filled=True)
        self._hollow_star = self._create_star_surface(self.size, filled=False)
        self.num_stars = 3
        star_w, star_h = self._filled_star.get_size()
        total_width = star_w * self.num_stars
        self.pos = [int(SCREEN_WIDTH/2 - total_width/2), 0]
        self.surface = pygame.Surface((total_width, star_h), pygame.SRCALPHA)
        
        # Track the animation state for each star
        # -1 means no animation, otherwise timestamp of start
        self._star_animation_start_ms = [-1] * self.num_stars
        self._easing = easing_functions.CubicEaseOut(start=0, end=1, duration=self.STAR_SPIN_DURATION_MS)
        self._last_filled_count = 0
        self._needs_redraw = True
        self._tada_scheduled_ms = -1
        self._heartbeat_start_ms = -1

        # Pre-create easing function for tada blink animation
        # Creates a smooth fade curve for blinking effect
        self._blink_easing = easing_functions.QuadEaseInOut(start=0, end=1, duration=100)

        self._render_surface(0)  # Force initial render

    def _create_star_surface(self, size: float, filled: bool) -> pygame.Surface:
        """Create a single anti-aliased star surface."""
        # Supersampling parameters
        factor = 4
        width = int(size * 1.2)
        height = int(size * 1.2)
        
        # High-res dimensions
        large_width = width * factor
        large_height = height * factor
        large_surface = pygame.Surface((large_width, large_height), pygame.SRCALPHA)
        
        # Calculate stroke width first
        stroke_width = 0 if filled else max(1, int(size * 0.1 * factor))
        
        # Calculate star vertices
        cx, cy = large_width // 2, large_height // 2
        outer_radius = (size * factor) // 2
        inner_radius = outer_radius * 0.382  # Golden ratio / star geometry
        
        # Since stroke is centered on the line, we shrink the hollow star's path
        # so its outer edge aligns with the filled star's edge
        if not filled:
            offset = stroke_width / 2.0
            outer_radius -= offset
            inner_radius -= offset

        points = []
        angle_step = math.pi / 5
        current_angle = -math.pi / 2  # Pointing up
        
        for i in range(10):
            radius = outer_radius if i % 2 == 0 else inner_radius
            points.append((
                cx + radius * math.cos(current_angle),
                cy + radius * math.sin(current_angle)
            ))
            current_angle += angle_step
        
        color = STAR_COLOR if filled else EMPTY_STAR_COLOR
        pygame.draw.polygon(large_surface, color, points, stroke_width)
        
        # Downsample for anti-aliasing
        return pygame.transform.smoothscale(large_surface, (width, height))

    def draw(self, current_score: int, now_ms: int) -> int:
        """Update score and trigger animations. Returns the number of stars earned."""
        # Earn a star for every min_win_score/3 points
        num_filled = min(self.num_stars, int(current_score / (self.min_win_score / 3.0)))

        if num_filled > self._last_filled_count:
            # Play star spin sound for any newly earned star(s)
            if self.sound_manager:
                self.sound_manager.play_starspin()

            for i in range(self._last_filled_count, num_filled):
                self._star_animation_start_ms[i] = now_ms
            
            # Schedule tada sound when the 3rd star is earned
            # Start after the 3rd star finishes spinning in (animation_duration_ms)
            if num_filled == 3 and self._last_filled_count < 3 and self.sound_manager:
                self._tada_scheduled_ms = now_ms + self.STAR_SPIN_DURATION_MS

        self._last_filled_count = num_filled
        self._needs_redraw = True
        return num_filled
        
    def _apply_per_star_blinking(self, star_surface: pygame.Surface, star_index: int, tada_elapsed_ms: int) -> pygame.Surface:
        """Apply blinking effect to a star surface during tada animation.

        Args:
            star_surface: The star surface to blink
            star_index: Index of the star (0-2), used to stagger blinks
            tada_elapsed_ms: Elapsed time since tada started

        Returns:
            The star surface with alpha applied if blinking, otherwise the original
        """
        # Stagger each star's blink by BLINK_STAR_OFFSET_MS
        star_blink_start = star_index * self.BLINK_STAR_OFFSET_MS
        star_elapsed = tada_elapsed_ms - star_blink_start

        # Star blinks for BLINK_DURATION_PER_STAR_MS after its staggered start
        if 0 <= star_elapsed < self.BLINK_DURATION_PER_STAR_MS * 3:
            opacity = self._get_blink_opacity(star_elapsed)
            # Create a copy to apply alpha
            blinking_surface = star_surface.copy()
            blinking_surface.set_alpha(int(255 * opacity))
            return blinking_surface

        return star_surface

    def _get_blink_opacity(self, elapsed_ms: int) -> float:
        """Calculate opacity for a single blink cycle."""
        position_in_blink = elapsed_ms % self.BLINK_DURATION_PER_STAR_MS

        # Fade out phase
        if position_in_blink < self.BLINK_FADE_OUT_MS:
            progress = position_in_blink / self.BLINK_FADE_OUT_MS
            opacity_change = (1.0 - self.BLINK_MIN_OPACITY) * self._blink_easing(progress)
            return 1.0 - opacity_change

        # Fade in phase
        fade_in_duration = self.BLINK_DURATION_PER_STAR_MS - self.BLINK_FADE_OUT_MS
        progress = (position_in_blink - self.BLINK_FADE_OUT_MS) / fade_in_duration
        opacity_change = (1.0 - self.BLINK_MIN_OPACITY) * self._blink_easing(progress)
        return self.BLINK_MIN_OPACITY + opacity_change

    def _render_surface(self, now_ms: int) -> None:
        """Render stars to the internal surface."""
        star_w = self._filled_star.get_width()
        star_h = self._filled_star.get_height()

        self.surface.fill((0, 0, 0, 0))

        # Calculate tada animation elapsed time if active
        tada_elapsed_ms = (now_ms - self._heartbeat_start_ms) if self._heartbeat_start_ms > 0 else -1

        for i in range(self.num_stars):
            x_pos = i * star_w
            is_filled = i < self._last_filled_count
            start_ms = self._star_animation_start_ms[i]

            scale = 1.0
            angle = 0.0

            # Scale/Rotate animation (when earning a star)
            if is_filled and start_ms > 0 and (now_ms - start_ms) < self.STAR_SPIN_DURATION_MS:
                elapsed = now_ms - start_ms
                progress = self._easing(elapsed)
                scale = max(0.0, progress)
                angle = (1.0 - progress) * 360

            # Get the base star to render
            star_to_draw = self._filled_star if is_filled else self._hollow_star

            # Apply scale/rotation if needed
            if scale != 1.0 or angle != 0.0:
                scaled_star = pygame.transform.rotozoom(star_to_draw, angle, scale)
                sw, sh = scaled_star.get_size()

                cx = x_pos + star_w / 2
                cy = star_h / 2
                render_pos = (cx - sw / 2, cy - sh / 2)
                star_surface = scaled_star
            else:
                render_pos = (x_pos, 0)
                star_surface = star_to_draw

            # Apply per-star blinking during tada animation
            if tada_elapsed_ms >= 0 and is_filled:
                star_surface = self._apply_per_star_blinking(star_surface, i, tada_elapsed_ms)

            self.surface.blit(star_surface, render_pos)

    def _update_tada_animation(self, now_ms: int) -> bool:
        """Update tada animation state and return whether it's active.

        Returns:
            True if tada animation is currently active
        """
        # Check if tada sound should play
        if self._tada_scheduled_ms > 0 and now_ms >= self._tada_scheduled_ms:
            if self.sound_manager:
                self.sound_manager.play_tada()
            self._tada_scheduled_ms = -1
            self._heartbeat_start_ms = now_ms

        # Check if tada animation is active
        if self._heartbeat_start_ms > 0:
            if (now_ms - self._heartbeat_start_ms) >= self.TADA_TOTAL_DURATION_MS:
                # Tada animation finished
                self._heartbeat_start_ms = -1
                self._render_surface(now_ms)
                return False
            return True

        return False

    def update(self, window: pygame.Surface, now_ms: int) -> None:
        """Render the stars to the window."""
        animation_active = any(
            start_ms > 0 and (now_ms - start_ms) < self.STAR_SPIN_DURATION_MS
            for start_ms in self._star_animation_start_ms
        )

        tada_active = self._update_tada_animation(now_ms)

        if animation_active or self._needs_redraw or tada_active:
            self._render_surface(now_ms)
            self._needs_redraw = animation_active or tada_active

        window.blit(self.surface, self.pos)


class NullStarsDisplay:
    """Null object for stars display."""
    
    def __init__(self) -> None:
        pass
        
    def draw(self, current_score: int, now_ms: int) -> int:
        return 0
        
    def update(self, window: pygame.Surface, now_ms: int) -> None:
        pass
