#!/usr/bin/env python3

import aiomqtt
import argparse
import asyncio
from datetime import datetime
import json
import logging
import os
import pygame
import random
import sys

from hardware.cubes_interface import CubesHardwareInterface
from core import app
from config import game_config
from hardware import cubes_to_game
from core.dictionary import Dictionary
from utils.pygameasync import events
import pygamegameasync
from core import tiles
from utils import hub75
from game_logging.game_loggers import OutputLogger, GameLogger, PublishLogger

MQTT_SERVER = game_config.MQTT_SERVER
my_open = open

logger = logging.getLogger(__name__)

async def publish_tasks_in_queue(publish_client: aiomqtt.Client, queue: asyncio.Queue, publish_logger: PublishLogger, last_messages: dict[str, str] | None = None) -> None:
    if last_messages is None:
        last_messages = {}

    while True:
        try:
            timestamp = None
            topic, message, retain, timestamp = await queue.get()

            # Publish retained messages if they changed.
            if not retain or last_messages.get(topic, "INIT") != message:
                await publish_client.publish(topic, message, retain=retain)
                last_messages[topic] = message
                logger.info(f"publishing: {topic}, {message}")
                publish_logger.log_mqtt_publish(topic, message, retain, timestamp)
        except asyncio.CancelledError:
            # Handle graceful shutdown            
            break
        except aiomqtt.exceptions.MqttCodeError as e:
            print(f"publish_tasks_in_queue failed {e}")
            # Don't exit on MqttCodeError, as it might be a transient issue
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"publish_tasks_in_queue failed {e}")
            sys.exit(1)


async def main(args: argparse.Namespace, dictionary: Dictionary, block_words: pygamegameasync.BlockWordsPygame, keyboard_player_number: int, seed: int, game_logger: GameLogger) -> None:
    # Set up loggers
    publish_logger = PublishLogger("output/output.publish.jsonl")
    output_logger = OutputLogger("output/output.jsonl")

    try:
        publish_logger.start_logging()
        game_logger.start_logging()
        if not args.replay:
            print(f"LOGGING SEED {seed}")
            game_logger.log_seed(seed)
            # Log the ABC countdown delay used in cubes_to_game.py
            game_logger.log_delay_ms(cubes_to_game.ABC_COUNTDOWN_DELAY_MS)

        async with aiomqtt.Client(MQTT_SERVER) as subscribe_client:
            async with aiomqtt.Client(MQTT_SERVER) as publish_client:
                publish_queue: asyncio.Queue = asyncio.Queue()
                hardware = CubesHardwareInterface()
                the_app = app.App(publish_queue, dictionary, hardware)
                
                await cubes_to_game.init(subscribe_client)
                # Clear any retained letters and borders from a previous run
                await cubes_to_game.clear_all_letters(publish_queue, 0)
                await cubes_to_game.clear_all_borders(publish_queue, 0)
                # Activate ABC start sequence at startup
                await cubes_to_game.activate_abc_start_if_ready(publish_queue, 0)
                if args.replay:
                    block_words.get_mock_mqtt_client()
                else:
                    await subscribe_client.subscribe("game/guess")

                # MQTT subscription is now handled in pygamegameasync main loop
                publish_task = asyncio.create_task(publish_tasks_in_queue(publish_client, publish_queue, publish_logger, {}),
                    name="mqtt publish handler")

                await block_words.main(the_app, subscribe_client, args.start, keyboard_player_number, publish_queue, game_logger, output_logger)

                # Wait for the publish queue to be empty before shutting down
                while not publish_queue.empty():
                    await asyncio.sleep(0.1)
                
                publish_queue.shutdown()
                publish_task.cancel()
                
                # Wait for the publish task to complete
                try:
                    await publish_task
                except asyncio.CancelledError:
                    pass
    finally:
        publish_logger.stop_logging()



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Legacy tags file no longer used (cube/right adopted)
    parser.add_argument('--start', action=argparse.BooleanOptionalAction)
    parser.add_argument("--keyboard-player-number", default=1, type=int, help="Player number (1 or 2) that uses keyboard input")
    parser.add_argument("--replay", type=str, help="Replay a game from a log file")
    parser.add_argument("--descent-mode", type=str, default="discrete", choices=["discrete", "timed"],
                       help="Descent strategy: discrete (classic) or timed")
    parser.add_argument("--timed-duration", type=int, default=120,
                       help="Duration in seconds for timed mode (default: 240 seconds / 4 minutes)")
    args = parser.parse_args()
    
    seed = 1
    if args.replay:
        delay_ms = 500  # Default for old replay files
        with open(args.replay, 'r') as f:
            try:
                # Read first line for seed
                first_event = json.loads(f.readline())
                if first_event.get("event_type") == "seed":
                    seed = first_event["seed"]
                    # Try to read second line for delay_ms
                    try:
                        second_event = json.loads(f.readline())
                        if second_event.get("event_type") == "delay_ms":
                            delay_ms = second_event["delay_ms"]
                    except (json.JSONDecodeError, IndexError):
                        pass  # Use default delay_ms if not found
                else:
                    f.seek(0)
            except (json.JSONDecodeError, IndexError):
                pass
        cubes_to_game.set_abc_countdown_delay(delay_ms)
    else:
        seed = int(datetime.now().timestamp())
    random.seed(seed)
    if os.environ.get("DEBUG"):
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        if not root.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
            root.addHandler(handler)
    else:
        logging.basicConfig(level=logging.INFO)
    pygame.mixer.init(frequency=24000, size=-16, channels=2)
    hub75.init()
    dictionary = Dictionary(game_config.MIN_LETTERS, game_config.MAX_LETTERS, open=my_open)
    dictionary.read(game_config.DICTIONARY_PATH, game_config.BINGOS_PATH)
    pygame.init()
    block_words = pygamegameasync.BlockWordsPygame(replay_file=args.replay or "", descent_mode=args.descent_mode, timed_duration_s=args.timed_duration)
    
    game_logger = GameLogger(None if args.replay else "output/game_replay.jsonl")
    try:
        asyncio.run(main(args, dictionary, block_words, args.keyboard_player_number-1, seed, game_logger))
        print("asyncio main done")
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.exception(e)
        # Still need to quit pygame to stop the window
        pygame.quit()
        sys.exit(1)
    finally:
        game_logger.stop_logging()
