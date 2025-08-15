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

import app
import cubes_to_game
from dictionary import Dictionary
from pygameasync import events
import pygamegameasync
import tiles
import hub75
import json
import pygame

class BaseLogger:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.log_f = None
        
    def start_logging(self):
        print(f"STARTING LOGGING {self.log_file}")
        if self.log_file:
            if self.log_file == "game_replay.jsonl":
                print("opening game_replay")
            self.log_f = open(self.log_file, "w")
    
    def stop_logging(self):
        if self.log_f:
            self.log_f.close()
            self.log_f = None
    
    def _write_event(self, event: dict):
        if not self.log_f:
            return
        self.log_f.write(json.dumps(event) + "\n")
        self.log_f.flush()

class OutputLogger(BaseLogger):
    def log_word_formed(self, word: str, player: int, score: int, now_ms: int):
        event = {
            "time": now_ms,
            "event_type": "word_formed",
            "word": word,
            "player": player,
            "score": score
        }
        self._write_event(event)
    
    def log_letter_position_change(self, x: int, y: int, now_ms: int):
        event = {
            "time": now_ms,
            "event_type": "letter_position",
            "x": x,
            "y": y,
        }
        self._write_event(event)

class GameLogger(BaseLogger):
    def log_seed(self, seed: int):
        event = {
            "event_type": "seed",
            "seed": seed
        }
        print(f">>>>>>>> logging seed {event}")
        self._write_event(event)
        
    def log_events(self, now_ms: int, events: dict):
        log_entry = {
            "timestamp_ms": now_ms,
            "events": events
        }
        
        self._write_event(log_entry)

class PublishLogger(BaseLogger):
    def log_mqtt_publish(self, topic: str, message, retain: bool, timestamp_ms: int):
        """Log MQTT publish event to JSONL file."""
        event = {
            "time": timestamp_ms,
            "topic": topic,
            "message": message,
            "retain": retain
        }
        self._write_event(event)

MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")
my_open = open

logger = logging.getLogger(__name__)

async def publish_tasks_in_queue(publish_client: aiomqtt.Client, queue: asyncio.Queue, publish_logger: PublishLogger) -> None:
    while True:
        try:
            timestamp = None
            topic, message, retain, timestamp = await queue.get()
            # Store last messages in dict if not already defined
            if not hasattr(publish_tasks_in_queue, 'last_messages'):
                publish_tasks_in_queue.last_messages = {}
                
            # Publish retained messages if they changed.
            if not retain or publish_tasks_in_queue.last_messages.get(topic, "INIT") != message:
                await publish_client.publish(topic, message, retain=retain)
                publish_tasks_in_queue.last_messages[topic] = message
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

        async with aiomqtt.Client(MQTT_SERVER) as subscribe_client:
            async with aiomqtt.Client(MQTT_SERVER) as publish_client:
                publish_queue: asyncio.Queue = asyncio.Queue()
                the_app = app.App(publish_queue, dictionary)
                
                await cubes_to_game.init(subscribe_client)
                # Clear any retained letters and borders from a previous run
                await cubes_to_game.clear_all_letters(publish_queue, 0)
                await cubes_to_game.clear_all_borders(publish_queue, 0)
                # Activate ABC start sequence at startup (if no moratorium active)
                await cubes_to_game.activate_abc_start_if_ready(publish_queue, 0)
                if args.replay:
                    block_words.get_mock_mqtt_client()
                else:
                    await subscribe_client.subscribe("game/guess")

                # MQTT subscription is now handled in pygamegameasync main loop
                publish_task = asyncio.create_task(publish_tasks_in_queue(publish_client, publish_queue, publish_logger),
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

BUNDLE_TEMP_DIR = "."

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Legacy tags file no longer used (cube/right adopted)
    parser.add_argument('--start', action=argparse.BooleanOptionalAction)
    parser.add_argument("--keyboard-player-number", default=1, type=int, help="Player number (1 or 2) that uses keyboard input")
    parser.add_argument("--replay", type=str, help="Replay a game from a log file")
    args = parser.parse_args()
    
    seed = 1
    if args.replay:
        with open(args.replay, 'r') as f:
            try:
                first_event = json.loads(f.readline())
                if first_event.get("event_type") == "seed":
                    seed = first_event["seed"]
                else:
                    f.seek(0)
            except (json.JSONDecodeError, IndexError):
                pass
    else:
        seed = int(datetime.now().timestamp())
    random.seed(seed)

    # logger.setLevel(logging.DEBUG)
    pygame.mixer.init(frequency=24000, size=-16, channels=2)
    hub75.init()
    dictionary = Dictionary(tiles.MIN_LETTERS, tiles.MAX_LETTERS, open=my_open)
    dictionary.read(f"{BUNDLE_TEMP_DIR}/sowpods.txt", f"{BUNDLE_TEMP_DIR}/bingos.txt")
    pygame.init()
    block_words = pygamegameasync.BlockWordsPygame(replay_file=args.replay or "")
    
    game_logger = GameLogger(None if args.replay else "game_replay.jsonl")
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