
import sys
import os
import pygame
import random
import time

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from rendering.rack_display import RackDisplay
from rendering.metrics import RackMetrics
from ui.guess_display import PreviousGuessesManager
from core import tiles

# Mock classes
class MockApp:
    def __init__(self):
        self.player_count = 1

class MockLetter:
    def __init__(self):
        self.locked_on = False
        self.letter = "A"

# Configuration
SCREEN_WIDTH = 192
SCREEN_HEIGHT = 256
SCALING_FACTOR = 3

def main():
    pygame.init()
    
    # Setup window
    window = pygame.display.set_mode((SCREEN_WIDTH * SCALING_FACTOR, SCREEN_HEIGHT * SCALING_FACTOR))
    pygame.display.set_caption("Falling Words Visualization")
    
    screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    
    # Initialize components
    mock_app = MockApp()
    rack_metrics = RackMetrics()
    mock_letter = MockLetter()
    
    # Setup Rack
    rack = RackDisplay(mock_app, rack_metrics, mock_letter, player=0)
    rack.running = True
    
    # Populate rack with some letters
    rack_tiles = [
        tiles.Tile("W", "0"), tiles.Tile("O", "1"), tiles.Tile("R", "2"), 
        tiles.Tile("D", "3"), tiles.Tile("S", "4"), tiles.Tile("!", "5")
    ]
    # Manually update rack properties since update_rack is async
    rack.tiles = rack_tiles
    rack.highlight_length = 0
    rack.select_count = 0
    rack.draw()
    
    # Setup Guesses
    guess_to_player = {}
    guesses_manager = PreviousGuessesManager(guess_to_player)
    
    # Populate guesses with a bunch of words to fill the screen
    dummy_guesses = [
        "HELLO", "WORLD", "PYTHON", "GAMING", "TEST"
    ]

    now_ms = pygame.time.get_ticks()
    for guess in dummy_guesses:
        # Simulate time passing for adds
        now_ms += 100
        guesses_manager.add_guess(dummy_guesses[:dummy_guesses.index(guess)+1], guess, player=0, now_ms=now_ms)

    print(f"Added {len(dummy_guesses)} guesses to manager")
        
    
    # Melting animation state
    melt_surface = None
    melt_columns = []
    
    clock = pygame.time.Clock()
    running = True
    game_over = False
    frame_count = 0

    print("controls:")
    print("  SPACE: Trigger Melting Effect")
    print("  R: Reset")
    print("  ESC: Quit")

    while running:
        current_time_ms = pygame.time.get_ticks()
        frame_count += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    if not game_over:
                        game_over = True
                        print("Melting triggered!")
                        # Capture surface next frame
                elif event.key == pygame.K_r:
                    game_over = False
                    melt_surface = None
                    melt_columns = []
                    rack.running = True
                    print("Reset.")

        # Auto-trigger after 60 frames
        if frame_count == 60 and not game_over:
            print(f"Frame {frame_count}: Capturing before_melt BEFORE setting game_over=True")
            pygame.image.save(screen, "before_melt.png")
            print("Saved before_melt.png")
            game_over = True
            print(f"Frame {frame_count}: Set game_over=True")
            print("Auto-triggered melting effect!")

        if not game_over or melt_surface is None:
            # Normal Draw for capture
            screen.fill((0, 0, 0))

            if frame_count == 60:
                print("Frame 60 - Before guesses update")

            # Draw components
            if frame_count == 1:
                print(f"Guesses in manager: {len(guesses_manager.previous_guesses_display.previous_guesses)}")
                print(f"Screen size: {screen.get_size()}")
                print(f"POSITION_TOP: {guesses_manager.previous_guesses_display.POSITION_TOP}")

            guesses_manager.update(screen, current_time_ms, game_over=False)

            # Manual blit of guesses surface for debugging
            guess_surf = guesses_manager.previous_guesses_display.surface

            if frame_count == 59:
                # Debug: check actual pixel values across entire surface
                print(f"Checking guesses surface (size {guess_surf.get_size()}) pixels:")
                found_colored = False
                for y in range(guess_surf.get_height()):
                    for x in range(0, guess_surf.get_width(), 20):
                        pixel = guess_surf.get_at((x, y))
                        if pixel[3] > 100:  # Check alpha
                            print(f"  Pixel at ({x}, {y}): {pixel}")
                            found_colored = True
                            break
                    if found_colored:
                        break
                if not found_colored:
                    print("  No colored pixels found!")

            screen.blit(guess_surf, (0, guesses_manager.previous_guesses_display.POSITION_TOP))

            if frame_count == 60:
                print("Frame 60 - After guesses update, screen has content")
                pygame.image.save(screen, "debug_after_guesses_update.png")
            
            # Force rack to draw tiles even if 'game_over' is True
            # We bypass rack.update's check for self.running by behaving as if passing
            # but rack.running is actually controlled by SPACE.
            # Let's ensure rack.draw() is called and we blit the surface manually if needed
            # or just rely on rack.update drawing tiles if running=True.
            
            # For visualization, we need to correctly handle the rack state
            if not game_over:
                 rack.update(screen, current_time_ms)
            else:
                 # In the falling state, force draw the rack's internal surface
                 # which contains the tiles.
                 screen.blit(rack.surface, rack.rack_metrics.get_rect().topleft)

            if game_over and melt_surface is None:
                print("Capturing melt surface...")
                melt_surface = screen.copy()
                pygame.image.save(melt_surface, "melt_initial_capture.png")
                print("Saved melt_initial_capture.png")
                
                width, height = melt_surface.get_size()
                melt_columns = []
                for x in range(width):
                    melt_columns.append({
                        'y': 0.0,
                        'vel': 0.0,                        # Start stationary
                        'acc': random.uniform(0.1, 0.5),  # Gravity variance
                        'delay': random.uniform(0, 30)    # Start delay frames
                    })

        else:
            # Melt Draw
            screen.fill((0, 0, 0))
            width, height = melt_surface.get_size()

            for x in range(width):
                col = melt_columns[x]
                if col['delay'] > 0:
                    col['delay'] -= 1
                else:
                    col['vel'] += col['acc']
                    col['y'] += col['vel']

                # Blit column at new position (pygame clips if off-screen)
                dest_y = int(col['y'])
                if dest_y < height:
                    screen.blit(melt_surface, (x, dest_y), area=pygame.Rect(x, 0, 1, height))
            
            # Capture a frame of the melting
            if current_time_ms % 1000 < 20: # roughly once a second
                 pygame.image.save(screen, f"melt_progress_{int(current_time_ms)}.png")

            # Auto-exit after 3 seconds of melting
            if frame_count > 60 + 180:
                running = False

        if frame_count == 59:
            print(f"Frame {frame_count}: End of frame, saving final_frame_59.png")
            pygame.image.save(screen, "final_frame_59.png")

        # Scale to window
        pygame.transform.scale(screen, window.get_rect().size, window)
        pygame.display.flip()
        clock.tick(60)
        
    pygame.quit()

if __name__ == "__main__":
    main()
