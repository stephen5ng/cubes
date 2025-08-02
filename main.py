#!/usr/bin/env python3

import aiomqtt
import argparse
import asyncio
import json
import logging
import os
import platform
import pygame
import random
from datetime import datetime

import app
import cubes_to_game
from dictionary import Dictionary
from pygameasync import events
import pygamegameasync
import tiles
import hub75
import publish_logger

MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")
my_open = open

logger = logging.getLogger(__name__)

# JSONL logger for word formations
word_logger = None

def setup_word_logger():
    """Setup JSONL logger for word formations."""
    global word_logger
    word_logger = open("game_replay_output.jsonl", "w")

def log_word_formed(word: str, player: int, score: int):
    """Log new word formation event to JSONL file."""
    if word_logger:
        event = {
            "event_type": "word_formed",
            "word": word,
            "player": player,
            "score": score
        }
        word_logger.write(json.dumps(event) + "\n")
        word_logger.flush()

def cleanup_word_logger():
    """Close the word logger."""
    global word_logger
    if word_logger:
        word_logger.close()
        word_logger = None

async def publish_tasks_in_queue(publish_client: aiomqtt.Client, queue: asyncio.Queue) -> None:
    while True:
        topic, message, retain = await queue.get()
        # print(f"publish_tasks_in_queue: {topic}, {message}, {retain}")
        # Store last messages in dict if not already defined
        if not hasattr(publish_tasks_in_queue, 'last_messages'):
            publish_tasks_in_queue.last_messages = {}
            
        # Publish retained messages if they changed.
        if not retain or publish_tasks_in_queue.last_messages.get(topic, None) != message:
            # print(f"get: {publish_tasks_in_queue.last_messages.get(topic, '')}, {publish_tasks_in_queue.last_messages.get(topic, '') != message}")
            await publish_client.publish(topic, message, retain=retain)
            publish_tasks_in_queue.last_messages[topic] = message
            logger.info(f"publishing: {topic}, {message}")
            publish_logger.log_mqtt_publish(topic, message, retain)
            # print(f"publishing: {topic}, {message}")



async def main(args: argparse.Namespace, dictionary: Dictionary, block_words: pygamegameasync.BlockWordsPygame, keyboard_player_number: int) -> None:
    setup_word_logger()
    publish_logger.setup_publish_logger()
    
    async with aiomqtt.Client(MQTT_SERVER) as subscribe_client:
        async with aiomqtt.Client(MQTT_SERVER) as publish_client:
            publish_queue: asyncio.Queue = asyncio.Queue()
            the_app = app.App(publish_queue, dictionary)
            the_app.set_word_logger(log_word_formed)
            
            await cubes_to_game.init(subscribe_client, args.tags)
            if args.replay:
                block_words.get_mock_mqtt_client()
            else:
                await subscribe_client.subscribe("game/guess")

            # MQTT subscription is now handled in pygamegameasync main loop
            publish_task = asyncio.create_task(publish_tasks_in_queue(publish_client, publish_queue),
                name="mqtt publish handler")

            await block_words.main(the_app, subscribe_client, args.start, keyboard_player_number, publish_queue)

            publish_queue.shutdown()
            publish_task.cancel()
            cleanup_word_logger()
            publish_logger.cleanup_publish_logger()

BUNDLE_TEMP_DIR = "."

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tags", default="tag_ids.txt", type=str)
    parser.add_argument('--start', action=argparse.BooleanOptionalAction)
    parser.add_argument("--keyboard-player-number", default=1, type=int, help="Player number (1 or 2) that uses keyboard input")
    parser.add_argument("--replay", type=str, help="Replay a game from a log file")
    args = parser.parse_args()
    
    random.seed(1)

    # logger.setLevel(logging.DEBUG)
    pygame.mixer.init(frequency=24000, size=-16, channels=2)
    hub75.init()
    dictionary = Dictionary(tiles.MIN_LETTERS, tiles.MAX_LETTERS, open=my_open)
    dictionary.read(f"{BUNDLE_TEMP_DIR}/sowpods.txt", f"{BUNDLE_TEMP_DIR}/bingos.txt")
    pygame.init()
    block_words = pygamegameasync.BlockWordsPygame(replay_file=args.replay)
    try:
        asyncio.run(main(args, dictionary, block_words, args.keyboard_player_number-1))
    finally:
        cleanup_word_logger()
        publish_logger.cleanup_publish_logger()
        pygame.quit()