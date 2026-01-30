import pytest
import pygame
import pygame.freetype
from rendering.text_renderer import TextRectRenderer, VICTORY_PALETTE
from ui.guess_display import PreviousGuessesDisplay
from config.player_config import PlayerConfigManager

def test_victory_animation_state():
    """Verify TextRectRenderer handles animation time and bouncing."""
    pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
        
    font = pygame.freetype.Font(None, 20)
    rect = pygame.Rect(0, 0, 100, 100)
    trr = TextRectRenderer(font, rect)
    
    # Should start with animation time = 0
    assert trr.animation_time == 0.0
    
    words = ["TEST", "TEST2"]
    colors = [pygame.Color("white"), pygame.Color("white")]
    
    # Render 1 frame with animate=True -> animation time increases
    trr.render(words, colors, animate=True)
    assert trr.animation_time > 0.0
    
    # Render with animate=False -> time stays same
    current_time = trr.animation_time
    trr.render(words, colors, animate=False)
    assert trr.animation_time == current_time
    
    # Verify palette exists
    assert len(VICTORY_PALETTE) > 0

def test_festive_display_drive():
    """Verify PreviousGuessesDisplay drives the festive animation only when game over."""
    pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
        
    font_size = 20
    
    config_manager = PlayerConfigManager(letter_width=20)
    
    display = PreviousGuessesDisplay(font_size, {}, config_manager=config_manager)
    
    # Add content
    display.add_guess(["TEST"], "TEST", 0, 0)
    
    # Initial state
    renderer = display._text_rect_renderer
    initial_time = renderer.animation_time
    
    window = pygame.Surface((800, 600))
    
    # Update with game_over=False -> No animation
    display.update(window, 0, game_over=False)
    assert renderer.animation_time == initial_time
    
    # Update with game_over=True -> Animation drives
    display.update(window, 0, game_over=True)
    assert renderer.animation_time > initial_time
