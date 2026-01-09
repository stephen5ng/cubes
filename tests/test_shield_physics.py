import argparse
import os
import sys
import pygame
import logging
import asyncio
from unittest.mock import Mock, AsyncMock
from core.app import App
from core import dictionary
from game.game_state import Game
from game.components import Shield
from config import game_config
from rendering.metrics import RackMetrics
from systems.sound_manager import SoundManager
from game_logging.game_loggers import GameLogger, OutputLogger

# 1. Setup Environment
parser = argparse.ArgumentParser(description="Test Shield Physics")
parser.add_argument("--visual", action="store_true", help="Show the game window")
args = parser.parse_args()

if not args.visual:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_mock_hardware():
    """Create a mock hardware interface with necessary async methods."""
    hw = Mock()
    hw.get_started_cube_sets.return_value = []
    hw.has_player_started_game.return_value = True
    
    async_methods = [
        'clear_remaining_abc_cubes', 'load_rack', 'guess_last_tiles',
        'unlock_all_letters', 'clear_all_borders', 'accept_new_letter',
        'old_guess', 'good_guess', 'bad_guess', 'guess_tiles'
    ]
    for method in async_methods:
        setattr(hw, method, AsyncMock())
        
    hw.letter_lock = AsyncMock(return_value=False)
    return hw

def create_game_instance():
    """Initialize Game with real dependencies and mocked hardware."""
    real_dictionary = dictionary.Dictionary(game_config.MIN_LETTERS, game_config.MAX_LETTERS)
    mock_hardware = create_mock_hardware()
    app = App(publish_queue=None, dictionary=real_dictionary, hardware_interface=mock_hardware)
    
    rack_metrics = RackMetrics()
    sound_manager = SoundManager()
    
    return Game(
        the_app=app,
        letter_font=rack_metrics.font,
        game_logger=GameLogger(None),
        output_logger=OutputLogger(None),
        sound_manager=sound_manager,
        rack_metrics=rack_metrics,
        letter_beeps=sound_manager.get_letter_beeps(),
        descent_mode="discrete"
    )

def setup_scenario(game):
    """Setup the specific test scenario: Shield vs Falling Letter."""
    game.running = True
    
    # Add Shield at Y=400
    shield_y = 400
    shield = Shield((100, shield_y), "SHIELD", 100, 0, 0)
    game.shields.append(shield)
    
    # Reset Letter
    game.letter.game_area_offset_y = 0 
    game.letter.start(0)
    game.letter.letter = "A"
    
    return shield

def run_test_sync():
    asyncio.run(run_test())

async def run_test():
    pygame.init()
    
    game = create_game_instance()
    window = pygame.display.set_mode((game_config.SCREEN_WIDTH, game_config.SCREEN_HEIGHT))
    if args.visual:
        pygame.display.set_caption("Visual Shield Physics Test")

    shield = setup_scenario(game)
    
    clock = pygame.time.Clock()
    frame_count = 0
    max_frames = 600 # 10s timeout
    collision_detected = False
    running = True
    
    logger.info(f"Starting simulation. Shield Y: {shield.rect.y}")
    
    while running and frame_count < max_frames:
        if args.visual:
            if pygame.event.peek(pygame.QUIT):
                running = False
            window.fill((0, 0, 0))
            
        await game.update(window, frame_count * 16)
        
        # Check collision
        if not shield.active and not collision_detected:
            collision_detected = True
            logger.info(f"Collision at frame {frame_count}. Letter bounced to Y: {game.letter.pos[1]}")
            
            if args.visual:
                logger.info("Visual mode: Auto-exiting in 1s...")
                max_frames = min(max_frames, frame_count + 60)
            else:
                running = False # Stop immediately in headless
                
        if args.visual:
            pygame.display.flip()
            clock.tick(60)
            await asyncio.sleep(0)

        frame_count += 1
        
    # Validation
    if not collision_detected:
        logger.error("FAILED: Shield never hit.")
        sys.exit(1)
        
    if game.letter.pos[1] >= 400:
         logger.error(f"FAILED: Letter didn't bounce up (Y={game.letter.pos[1]}).")
         sys.exit(1)
         
    logger.info("PASSED: Shield collision verified.")
    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    run_test_sync()
