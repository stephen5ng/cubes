"""Integration test for the game using production setup and game loop.

This test uses production code to verify the complete game system works together.
"""

import asyncio
from io import StringIO
import pygame
import random

from core import app, dictionary
from game_logging.game_loggers import GameLogger, OutputLogger
from hardware import cubes_to_game
import pygamegameasync
from testing.mock_mqtt_client import MockMqttClient


async def test_integration():
    """Integration test using production setup_game() and run_single_frame()."""
    print("=== INTEGRATION TEST ===")
    print("Testing complete game system with production code")

    # Initialize pygame
    pygame.init()
    clock = pygame.time.Clock()

    # Random seed
    random.seed(1)

    # Setup dictionary
    my_open = lambda filename, mode: StringIO("\n".join([
        "arch", "fuzz", "line", "search", "online"
    ])) if filename == "sowpods.txt" else StringIO("\n".join([
        "search", "online"
    ]))

    a_dictionary = dictionary.Dictionary(3, 6, my_open)
    a_dictionary.read("sowpods.txt", "bingos.txt")

    # Create app and publish queue
    publish_queue = asyncio.Queue()
    the_app = app.App(publish_queue, a_dictionary)

    # Create BlockWordsPygame instance (creates window)
    block_words = pygamegameasync.BlockWordsPygame(
        replay_file="",
        descent_mode="discrete",
        timed_duration_s=120
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
    print("Setting up game with production code...")
    screen, keyboard_input, input_devices, mqtt_message_queue, _ = await block_words.setup_game(
        the_app, subscribe_client, publish_queue, game_logger, output_logger
    )

    print("\n*** GAME WINDOW RUNNING ***")
    print("Running game loop for 30 seconds...")
    print("ESC starts game automatically, X closes window.")
    print(f"Window size: {block_words._window.get_size()}")
    print(f"Screen size: {screen.get_size()}")

    # Setup for run_single_frame
    time_offset = 0

    # Run for 30 seconds (1800 frames at 60 FPS)
    running = True
    frame_count = 0
    max_frames = 1800

    # Inject ESC keypress on first frame to start the game
    esc_injected = False

    while running and frame_count < max_frames:
        # Inject ESC key on first frame
        if not esc_injected:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
            esc_injected = True
        # Call the PRODUCTION game loop!
        # run_single_frame handles all pygame events internally (including QUIT and keyboard)
        should_exit, time_offset = await block_words.run_single_frame(
            screen, keyboard_input, input_devices,
            mqtt_message_queue, publish_queue, time_offset
        )

        if should_exit:
            print("Game requested exit")
            running = False
            break

        # Print progress and state every 5 seconds
        if frame_count % 300 == 0:
            seconds_remaining = (max_frames - frame_count) // 60
            print(f"  {seconds_remaining}s remaining... ", end="")
            if block_words.game.running:
                letter = block_words.game.letter.letter
                rack_running = block_words.game.racks[0].running
                print(f"Game running! letter='{letter}' rack={rack_running}")
            else:
                print("Game NOT running (press ESC to start)")

        frame_count += 1
        clock.tick(60)  # 60 FPS

    print("\nStopping game...")
    if block_words.game and block_words.game.running:
        await block_words.game.stop(pygame.time.get_ticks())

    print("Closing window...")
    pygame.quit()
    print("=== TEST COMPLETE ===")
    print("✓ Integration test passed!")


if __name__ == "__main__":
    asyncio.run(test_integration())
