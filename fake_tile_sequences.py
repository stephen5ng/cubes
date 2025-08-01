#! /usr/bin/env python

import aiomqtt
import argparse
import asyncio
import os
import random

MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")

def get_lines(filename: str) -> list[str]:
    with open(filename, 'r') as f:
        lines = f.readlines()
        return [line.strip() for line in lines]

async def pub(sleep_duration_s: int, identical: bool, players: list[int]) -> None:
    all_cube_ids = get_lines("cube_ids.txt")
    all_tag_ids = get_lines("tag_ids.txt")
    
    # Split into player groups (first 6 for p0, last 6 for p1)
    p0_cubes = all_cube_ids[:6]
    p1_cubes = all_cube_ids[6:]
    p0_tags = all_tag_ids[:6]
    p1_tags = all_tag_ids[6:]
    
    # Add empty tag option to both players
    p0_tags.append("")
    p1_tags.append("")
    
    # Initialize counters for each player
    p0_count = 0
    p1_count = 0

    async with aiomqtt.Client(MQTT_SERVER) as client:
        while True:
            if identical:
                # Generate one random sequence and send to both players
                cube_ix = random.randint(0, len(p0_cubes) - 1)
                tag_ix = random.randint(0, len(p0_tags) - 1)
                
                # Alternate which player gets the message first
                if p0_count % 2 == 0:
                    await client.publish(f"cube/nfc/{p0_cubes[cube_ix]}", payload=p0_tags[tag_ix])
                    await client.publish(f"cube/nfc/{p1_cubes[cube_ix]}", payload=p1_tags[tag_ix])
                else:
                    await client.publish(f"cube/nfc/{p1_cubes[cube_ix]}", payload=p1_tags[tag_ix])
                    await client.publish(f"cube/nfc/{p0_cubes[cube_ix]}", payload=p0_tags[tag_ix])
                p0_count += 1
                p1_count += 1
            else:
                # Original random behavior, but only for selected players
                if len(players) == 1:
                    player = players[0] - 1  # Convert 1/2 to 0/1
                else:
                    player = random.randint(0, 1)
                if player == 0 and 1 in players:
                    p0_count += 1
                    cubes = p0_cubes
                    tags = p0_tags
                elif player == 1 and 2 in players:
                    p1_count += 1
                    cubes = p1_cubes
                    tags = p1_tags
                else:
                    await asyncio.sleep(sleep_duration_s)
                    continue
                
                cube = random.choice(cubes)
                tag = random.choice(tags)
                await client.publish(f"cube/nfc/{cube}", payload=tag)
            await asyncio.sleep(sleep_duration_s)

parser = argparse.ArgumentParser(description="Generate random cube sequences")
parser.add_argument("--duration", type=float, default=0.01,
                    help="Sleep duration in seconds (default: 0.01)")
parser.add_argument("--identical", action="store_true",
                    help="Send same random sequence to both players simultaneously")
parser.add_argument("--player", type=int, choices=[1, 2], action="append", default=[],
                    help="Select which player(s) to send messages to (default: both)")
args = parser.parse_args()

asyncio.run(pub(args.duration, args.identical, args.player))
