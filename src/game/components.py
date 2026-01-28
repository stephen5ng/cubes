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
    FADER_PLAYER_COLORS,
    SHIELD_ACCELERATION_RATE,
    SHIELD_INITIAL_SPEED_MULTIPLIER,
    STAR_COLOR,
    EMPTY_STAR_COLOR
)


class Score:
    """Displays and manages player score."""
    
    def __init__(self, the_app: app.App, player: int, rack_metrics) -> None:
        self.the_app = the_app
        self.player = player
        
        # Required dependency injection - no fallback!
        self.font = pygame.freetype.SysFont(FONT, rack_metrics.LETTER_SIZE)
        self.pos = [0, 0]
        self.x = SCREEN_WIDTH/3 * (player+1)
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
        self.pos[0] = int((self.midscreen if self.the_app.player_count == 1 else self.x) 
                          - self.surface.get_width()/2)

    def update_score(self, score: int) -> None:
        """Add points to the score."""
        self.score += score
        self.draw()

    def update(self, window: pygame.Surface) -> None:
        """Render the score to the window."""
        window.blit(self.surface, self.pos)


class Shield:
    """Flying text shield that shows scored words."""
    
    def __init__(self, base_pos: tuple[int, int], letters: str, score: int, player: int, now_ms: int) -> None:
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
        self.surface = self.font.render(self.letters, FADER_PLAYER_COLORS[self.player])[0]
        self.pos[0] = int(SCREEN_WIDTH/2 - self.surface.get_width()/2)

    def update(self, window: pygame.Surface, now_ms: int) -> None:
        """Update and render the shield animation."""
        if self.active:
            update_count = (now_ms - self.start_time_ms) / (1000.0/TICKS_PER_SECOND)

            # Calculate position by summing up all previous speed contributions
            # This is a geometric series: initial_speed * (1 - (1.05)^update_count) / (1 - 1.05)
            displacement = self.initial_speed * (1 - (self.acceleration_rate ** update_count)) / (1 - self.acceleration_rate)
            self.pos[1] = self.base_pos[1] + displacement
            window.blit(self.surface, self.pos)

            # Get the tightest rectangle around the content for collision detection.
            self.rect = self.surface.get_bounding_rect().move(self.pos[0], self.pos[1])

    def letter_collision(self) -> None:
        """Handle collision with falling letter."""
        self.active = False
        self.pos[1] = SCREEN_HEIGHT


class StarsDisplay:
    """Displays stars in the upper right hand corner."""

    def __init__(self, rack_metrics) -> None:
        self.size = rack_metrics.LETTER_SIZE * 0.7
        self._filled_star = self._create_star_surface(self.size, filled=True)
        self._hollow_star = self._create_star_surface(self.size, filled=False)
        self.num_stars = 3
        star_w, star_h = self._filled_star.get_size()
        total_width = star_w * self.num_stars
        self.pos = [SCREEN_WIDTH - total_width - 10, 0]
        self.surface = pygame.Surface((total_width, star_h), pygame.SRCALPHA)
        
        # Track the animation state for each star
        # -1 means no animation, otherwise timestamp of start
        self._star_animation_start_ms = [-1] * self.num_stars
        self._animation_duration_ms = 800
        self._easing = easing_functions.CubicEaseOut(start=0, end=1, duration=self._animation_duration_ms)
        self._last_filled_count = 0
        self._needs_redraw = True

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

    def draw(self, current_score: int, now_ms: int) -> None:
        """Update score and trigger animations."""
        num_filled = min(self.num_stars, current_score // 10)

        if num_filled > self._last_filled_count:
            for i in range(self._last_filled_count, num_filled):
                self._star_animation_start_ms[i] = now_ms

        self._last_filled_count = num_filled
        self._needs_redraw = True
        
    def _render_surface(self, now_ms: int) -> None:
        """Render stars to the internal surface."""
        star_w = self._filled_star.get_width()
        star_h = self._filled_star.get_height()

        self.surface.fill((0, 0, 0, 0))

        for i in range(self.num_stars):
            x_pos = i * star_w
            is_filled = i < self._last_filled_count
            start_ms = self._star_animation_start_ms[i]

            if is_filled and start_ms > 0 and (now_ms - start_ms) < self._animation_duration_ms:
                elapsed = now_ms - start_ms
                progress = self._easing(elapsed)
                scale = max(0.0, progress)
                angle = (1.0 - progress) * 360

                scaled_star = pygame.transform.rotozoom(self._filled_star, angle, scale)
                sw, sh = scaled_star.get_size()

                cx = x_pos + star_w / 2
                cy = star_h / 2
                self.surface.blit(scaled_star, (cx - sw / 2, cy - sh / 2))
            else:
                star = self._filled_star if is_filled else self._hollow_star
                self.surface.blit(star, (x_pos, 0))

    def update(self, window: pygame.Surface, now_ms: int) -> None:
        """Render the stars to the window."""
        animation_active = any(
            start_ms > 0 and (now_ms - start_ms) < self._animation_duration_ms
            for start_ms in self._star_animation_start_ms
        )

        if animation_active or self._needs_redraw:
            self._render_surface(now_ms)
            self._needs_redraw = animation_active

        window.blit(self.surface, self.pos)


class NullStarsDisplay:
    """Null object for stars display."""
    
    def __init__(self) -> None:
        pass
        
    def draw(self, current_score: int, now_ms: int) -> None:
        pass
        
    def update(self, window: pygame.Surface, now_ms: int) -> None:
        pass
