import pygame
import random
import math
from typing import List, Dict, Any
from rendering.text_renderer import TextRectRenderer, Blitter, VICTORY_PALETTE

class BalloonEffect:
    """Effect that makes words float up like balloons, optionally with festive colors."""

    def __init__(self, renderer: TextRectRenderer, words: List[str], colors: List[pygame.Color], start_offset_y: int, rainbow: bool = False):
        self.balloons: List[Dict[str, Any]] = []
        self.animation_time = 0.0
        self.rainbow = rainbow
        
        # Ensure positions are calculated
        renderer.update_pos_dict(words)
        
        for i, (word, color) in enumerate(zip(words, colors)):
            # Get relative position on the text renderer surface
            try:
                pos = renderer.get_pos(word)
            except KeyError:
                continue

            balloon = {
                'index': i,
                'speed_y': random.uniform(0.15, 0.35),
                'wobble_amp': random.uniform(2.0, 5.0),
                'wobble_speed': random.uniform(0.005, 0.01),
                'wobble_phase': random.uniform(0, 6.28),
                'drift_speed_x': random.choice([-1, 1]) * random.uniform(0.05, 0.2),
            }

            # Create grey "ghost" surface for the static word left behind
            ghost_color = (100, 100, 100, 255)
            balloon['ghost_surface'] = Blitter._render_word(renderer._font, word, ghost_color)

            if self.rainbow:
                # Select a random festive color (excluding white)
                festive_colors = [c for c in VICTORY_PALETTE if c != pygame.Color("white")]
                render_color = random.choice(festive_colors) if festive_colors else pygame.Color("magenta")
                
                # Render the word into a single surface with the festive color
                color_tuple = (render_color.r, render_color.g, render_color.b, render_color.a)
                balloon['surface'] = Blitter._render_word(renderer._font, word, color_tuple)
            else:
                # Render the word into a single surface with the original color
                color_tuple = (color.r, color.g, color.b, color.a)
                balloon['surface'] = Blitter._render_word(renderer._font, word, color_tuple)

            # Use float for smoother animation
            balloon['base_x'] = float(pos[0])
            balloon['base_y'] = float(pos[1] + start_offset_y)
            balloon['x'] = float(pos[0])
            balloon['y'] = float(pos[1] + start_offset_y)
            
            self.balloons.append(balloon)
            
    def update(self) -> None:
        """Update balloon positions and animation time."""
        # Advance animation time (similar speed to TextRectRenderer)
        self.animation_time += 0.005
        
        for b in self.balloons:
            b['y'] -= b['speed_y']
            b['wobble_phase'] += b['wobble_speed']
            
            # Update wind drift (accelerates slightly over time for a "gust" feel or just constant drift)
            # Simple constant drift (cross breeze)
            b['drift_x'] = b.get('drift_x', 0.0) + b.get('drift_speed_x', 0.1)
            
            # Calculate new x with wobble AND wind
            x_offset = math.sin(b['wobble_phase']) * b['wobble_amp']
            b['x'] = b['base_x'] + x_offset + b['drift_x']
            
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the balloons."""
        for b in self.balloons:
            # Draw the static grey word left behind
            surface.blit(b['ghost_surface'], (int(b['base_x']), int(b['base_y'])))
            
            # Draw the floating balloon
            surface.blit(b['surface'], (int(b['x']), int(b['y'])))

if __name__ == "__main__":
    import sys
    import os
    # Add src to path
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    import pygame.freetype
    pygame.init()
    
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Balloon Effect Preview")
    
    # Setup dummy data
    font = pygame.freetype.SysFont("Arial", 48)
    rect = pygame.Rect(0, 0, 800, 600)
    renderer = TextRectRenderer(font, rect)
    
    words = ["HELLO", "WORLD", "BALLOON", "EFFECT"]
    colors = [pygame.Color("red"), pygame.Color("green"), pygame.Color("blue"), pygame.Color("yellow")]
    
    # Init effect (rainbow=True to see full effect)
    balloon_effect = BalloonEffect(renderer, words, colors, start_offset_y=200, rainbow=True)
    
    clock = pygame.time.Clock()
    running = True
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                   # Reset
                   balloon_effect = BalloonEffect(renderer, words, colors, start_offset_y=200, rainbow=True)
        
        screen.fill((0, 0, 0))
        balloon_effect.update()
        balloon_effect.draw(screen)
        
        pygame.display.flip()
        clock.tick(60)
        
    pygame.quit()
