"""Integration test for the game using production setup and game loop.

This test uses production code to verify the complete game system works together.
"""

import asyncio
from io import StringIO
import pygame
import random
import logging
import pytest

from core import app, dictionary
from game_logging.game_loggers import GameLogger, OutputLogger
from hardware import cubes_to_game
from hardware.cubes_interface import CubesHardwareInterface
import pygamegameasync
from testing.mock_mqtt_client import MockMqttClient
from tests.fixtures.game_factory import async_test

from unittest.mock import patch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class MockClock:
    def __init__(self):
        self.time_ms = 0
        
    def tick(self, framerate=0):
        if framerate:
            self.time_ms += 1000 // framerate
        return 1000 // framerate
        
    def get_ticks(self):
        return self.time_ms

@async_test
async def test_integration():
    """Integration test using production setup_game() and run_single_frame()."""
    logger.info("=== INTEGRATION TEST ===")
    logger.info("Testing complete game system with production code")

    # Initialize pygame
    pygame.init()
    
    # Mock time
    mock_clock = MockClock()
    
    with patch('pygame.time.get_ticks', side_effect=mock_clock.get_ticks), \
         patch('pygame.time.Clock', return_value=mock_clock):
         
        clock = pygame.time.Clock()

        # Random seed
        random.seed(1)

        # Setup dictionary
        SOWPODS_CONTENT = "arch\nfuzz\nline\nsearch\nonline"
        BINGOS_CONTENT = "search\nonline"

        def mock_opener(filename, mode='r'):
            if filename == "sowpods.txt":
                return StringIO(SOWPODS_CONTENT)
            return StringIO(BINGOS_CONTENT)

        a_dictionary = dictionary.Dictionary(3, 6, mock_opener)
        a_dictionary.read("sowpods.txt", "bingos.txt")

        # Create app and publish queue
        publish_queue = asyncio.Queue()
        
        # FIX: Inject HardwareInterface
        hardware = CubesHardwareInterface()
        the_app = app.App(publish_queue, a_dictionary, hardware)

        # Create BlockWordsPygame instance (creates window)
        block_words = pygamegameasync.BlockWordsPygame(
            previous_guesses_font_size=30,
            remaining_guesses_font_size_delta=5, # Default delta
            replay_file="",
            descent_mode="discrete",
            descent_duration_s=120,
            record=False,
            continuous=False,
            one_round=False,
            min_win_score=0,
            stars=False
        )

        # Initialize cubes_to_game
        subscribe_client = MockMqttClient([])
        await cubes_to_game.init(subscribe_client)
        await cubes_to_game.clear_all_letters(publish_queue, 0)
        await cubes_to_game.clear_all_borders(publish_queue, 0)

        # Create loggers
        game_logger = GameLogger(None)
        output_logger = OutputLogger(None)

        # Use production setup
        logger.info("Setting up game with production code...")
        screen, keyboard_input, input_devices, mqtt_message_queue, _ = await block_words.setup_game(
            the_app, subscribe_client, publish_queue, game_logger, output_logger
        )

        logger.info("\n*** GAME WINDOW RUNNING ***")
        logger.info("Running game loop for 30 seconds...")
        logger.info("ESC starts game automatically, X closes window.")
        logger.info(f"Window size: {block_words._window.get_size()}")
        logger.info(f"Screen size: {screen.get_size()}")

        # Setup for run_single_frame
        time_offset = 0

        # Test configuration
        FPS = 60
        TEST_DURATION_SECONDS = 30
        MAX_FRAMES = FPS * TEST_DURATION_SECONDS
        LOG_INTERVAL_FRAMES = 300

        # Run for 30 seconds (1800 frames at 60 FPS)
        running = True
        frame_count = 0

        # Inject ESC keypress on first frame to start the game
        esc_injected = False

        while running and frame_count < MAX_FRAMES:
            # Inject ESC key on first frame
            if not esc_injected:
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
                esc_injected = True
            # Call the PRODUCTION game loop!
            # run_single_frame handles all pygame events internally (including QUIT and keyboard)
            should_exit, time_offset, _exit_code = await block_words.run_single_frame(
                screen, keyboard_input, input_devices,
                mqtt_message_queue, publish_queue, time_offset
            )

            if should_exit:
                logger.info("Game requested exit")
                running = False
                break

            # Print progress and state every 5 seconds
            if frame_count % LOG_INTERVAL_FRAMES == 0:
                seconds_remaining = (MAX_FRAMES - frame_count) // FPS
                msg = f"  {seconds_remaining}s remaining... "
                if block_words.game.running:
                    letter = block_words.game.letter.letter
                    rack_running = block_words.game.racks[0].running
                    msg += f"Game running! letter='{letter}' rack={rack_running}"
                else:
                    msg += "Game NOT running (press ESC to start)"
                logger.info(msg)

            frame_count += 1
            clock.tick(FPS)  # 60 FPS

        logger.info("\nStopping game...")
        if block_words.game and block_words.game.running:
            await block_words.game.stop(pygame.time.get_ticks(), 0)

        logger.info("Closing window...")
        pygame.quit()
        logger.info("=== TEST COMPLETE ===")
        assert block_words.game is not None, "Game object should be initialized"
        assert not block_words.game.running, "Game should be stopped after test"
        logger.info("✓ Integration test passed!")


if __name__ == "__main__":
    asyncio.run(test_integration())
