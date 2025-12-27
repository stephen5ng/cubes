#! /usr/bin/env python

import aiomqtt
import argparse
import asyncio
import os
import random

MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")

def _player_cubes() -> tuple[list[str], list[str]]:
    """Return cube ID lists for P0 and P1 using numeric cube IDs.

    P0: 1-6
    P1: 11-16
    """
    p0 = [str(i) for i in range(1, 7)]
    p1 = [str(i) for i in range(11, 17)]
    return p0, p1

async def pub(sleep_duration_s: int, identical: bool, players: list[int]) -> None:
    # Use numeric cube IDs; no NFC tag IDs
    p0_cubes, p1_cubes = _player_cubes()
    
    # Initialize counters for each player
    p0_count = 0
    p1_count = 0

    async with aiomqtt.Client(MQTT_SERVER) as client:
        # Track current letters on cubes
        cube_to_letter = {}

        async def _consume_letters():
            await client.subscribe("cube/+/letter")
            async for message in client.messages:
                topic = str(message.topic)
                if not topic.startswith("cube/") or not topic.endswith("/letter"):
                    continue
                cube_id = topic.split("/")[1]
                try:
                    payload = message.payload.decode() if message.payload else ""
                except Exception:
                    payload = ""
                cube_to_letter[cube_id] = payload

        consumer_task = asyncio.create_task(_consume_letters())

        def group_ready(group_cubes: list[str]) -> bool:
            # Ready only if all six have a non-space, non-empty letter
            if not group_cubes:
                return False
            for c in group_cubes:
                letter = cube_to_letter.get(c, "")
                if not letter or letter == " ":
                    return False
            return True

        def pick_sender_and_neighbor(cubes: list[str]) -> tuple[str, str]:
            """Pick a sender cube and a neighbor cube (or empty string to clear).

            Ensures neighbor is either different from sender or empty string.
            """
            sender_ix = random.randint(0, len(cubes) - 1)
            sender = cubes[sender_ix]
            # Choose to clear link ~1/7 of the time
            if random.randint(0, len(cubes)) == 0:
                return sender, ""
            # Otherwise choose a different neighbor cube
            neighbor_ix = sender_ix
            while neighbor_ix == sender_ix:
                neighbor_ix = random.randint(0, len(cubes) - 1)
            neighbor = cubes[neighbor_ix]
            return sender, neighbor

        while True:
            if identical:
                # Only shuffle when both groups have all letters
                if group_ready(p0_cubes) and group_ready(p1_cubes):
                    # Pick same relative indices for both players
                    sender_ix = random.randint(0, len(p0_cubes) - 1)
                    # Clear ~1/7th of the time
                    if random.randint(0, len(p0_cubes)) == 0:
                        p0_sender, p0_neighbor = p0_cubes[sender_ix], ""
                        p1_sender, p1_neighbor = p1_cubes[sender_ix], ""
                    else:
                        neighbor_ix = sender_ix
                        while neighbor_ix == sender_ix:
                            neighbor_ix = random.randint(0, len(p0_cubes) - 1)
                        p0_sender, p0_neighbor = p0_cubes[sender_ix], p0_cubes[neighbor_ix]
                        p1_sender, p1_neighbor = p1_cubes[sender_ix], p1_cubes[neighbor_ix]

                    if p0_count % 2 == 0:
                        await client.publish(f"cube/right/{p0_sender}", payload=p0_neighbor, retain=True)
                        await client.publish(f"cube/right/{p1_sender}", payload=p1_neighbor, retain=True)
                    else:
                        await client.publish(f"cube/right/{p1_sender}", payload=p1_neighbor, retain=True)
                        await client.publish(f"cube/right/{p0_sender}", payload=p0_neighbor, retain=True)
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
                elif player == 1 and 2 in players:
                    p1_count += 1
                    cubes = p1_cubes
                else:
                    await asyncio.sleep(sleep_duration_s)
                    continue
                # Only shuffle when this group has all letters
                if group_ready(cubes):
                    sender, neighbor = pick_sender_and_neighbor(cubes)
                    await client.publish(f"cube/right/{sender}", payload=neighbor, retain=True)
            await asyncio.sleep(sleep_duration_s)

parser = argparse.ArgumentParser(description="Generate random cube neighbor sequences (cube/right) using numeric cube IDs")
parser.add_argument("--duration", type=float, default=0.01,
                    help="Sleep duration in seconds (default: 0.01)")
parser.add_argument("--identical", action="store_true",
                    help="Send same random sequence to both players simultaneously")
parser.add_argument("--player", type=int, choices=[1, 2], action="append", default=[],
                    help="Select which player(s) to send messages to (default: both)")
args = parser.parse_args()

asyncio.run(pub(args.duration, args.identical, args.player))
