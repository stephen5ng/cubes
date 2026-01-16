import pytest
import pygame
import pygame.freetype
from rendering.text_renderer import TextRectRenderer
from ui.guess_display import PreviousGuessesDisplay

def test_rainbow_animation_state():
    """Verify TextRectRenderer handles hue offset cycling."""
    pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
        
    font = pygame.freetype.Font(None, 20)
    rect = pygame.Rect(0, 0, 100, 100)
    trr = TextRectRenderer(font, rect)
    
    # Should start with hue offset = 0
    assert trr.hue_offset == 0.0
    
    words = ["TEST"]
    colors = [pygame.Color("white")]
    
    # Render 1 frame -> hue offset increases
    trr.render(words, colors)
    assert trr.hue_offset == 2.0
    
    # Render 180 frames (total 360 degrees rotation)
    for _ in range(179):
        trr.render(words, colors)
        
    # 2.0 * 180 = 360 -> wraps to 0.0
    assert trr.hue_offset == 0.0

def test_rainbow_display_drive():
    """Verify PreviousGuessesDisplay drives the rainbow animation."""
    pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
        
    font_size = 20
    display = PreviousGuessesDisplay(font_size, {})
    
    # Add content
    display.add_guess(["TEST"], "TEST", 0, 0)
    
    # Initial state (add_guess calls update which calls render -> increments hue)
    renderer = display._text_rect_renderer
    initial_hue = renderer.hue_offset
    assert initial_hue > 0
    
    # Update should drive animation
    window = pygame.Surface((800, 600))
    display.update(window, 0)
    
    assert renderer.hue_offset == initial_hue + 2.0
