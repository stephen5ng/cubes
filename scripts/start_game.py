#! /usr/bin/env python3

import aiomqtt
import argparse
import asyncio
import os
from typing import Dict, List, Tuple

MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")


def get_lines(filename: str) -> list[str]:
    with open(filename, 'r') as f:
        lines = f.readlines()
        return [line.strip() for line in lines]



async def _start_letter_consumer(client: aiomqtt.Client, cube_to_letter: Dict[str, str]) -> None:
    """Subscribe to cube letter topics and keep map updated."""
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
        print(f"payload: {payload} cube_to_letter {cube_to_letter}")


async def align_abc(sleep_duration_s: float) -> None:
    """Monitor cube letters and align ABC by publishing A->B, B->C when groups show only A/B/C."""
    all_cube_ids = get_lines("assets/data/cube_ids.txt")

    p0_cubes = all_cube_ids[:6]
    p1_cubes = all_cube_ids[6:]
    print(f"p0_cubes {p0_cubes} p1_cubes {p1_cubes}")
    
    # Track last ABC state to detect changes
    p0_last_abc_state = None
    p1_last_abc_state = None
    async with aiomqtt.Client(MQTT_SERVER) as client:
        cube_to_letter: Dict[str, str] = {}
        consumer_task = asyncio.create_task(_start_letter_consumer(client, cube_to_letter))
        try:
            while True:
                # Process each group independently
                for i, group_cubes in enumerate((p0_cubes, p1_cubes)):
                    if not group_cubes:
                        continue
                    
                    # Get all non-empty letters from this group
                    letters = {cube_to_letter.get(c, "") for c in group_cubes}
                    letters.discard("")
                    letters.discard(" ")
                    # print(f"group_cubes {group_cubes} letters: {letters}")
                    
                    # Check if we have A, B, C present
                    has_abc = {"A", "B", "C"}.issubset(letters)
                    
                    # Get last state for this group
                    if i == 0:  # P0 group
                        last_abc_state = p0_last_abc_state
                    else:  # P1 group  
                        last_abc_state = p1_last_abc_state
                    
                    # Trigger game start on transition from non-ABC to ABC
                    if has_abc and not last_abc_state:
                        # Map letters to cubes and publish neighbor cube IDs
                        cubes_by_letter = {cube_to_letter.get(c, ""): c for c in group_cubes if cube_to_letter.get(c)}
                        cube_a = cubes_by_letter.get("A")
                        cube_b = cubes_by_letter.get("B")
                        cube_c = cubes_by_letter.get("C")
                        if cube_a and cube_b and cube_c:
                            player_name = "P0" if i == 0 else "P1"
                            print(f"start_game STARTING GAME for {player_name}")
                            # Publish direct neighbor cube IDs on new protocol
                            await client.publish(f"cube/right/{cube_a}", payload=cube_b)
                            await client.publish(f"cube/right/{cube_b}", payload=cube_c)
                    
                    # Update last state for this group
                    if i == 0:
                        p0_last_abc_state = has_abc
                    else:
                        p1_last_abc_state = has_abc
                        
                await asyncio.sleep(sleep_duration_s)
        finally:
            consumer_task.cancel()


def main():
    parser = argparse.ArgumentParser(description="Align ABC for starting game")
    parser.add_argument("--duration", type=float, default=0.05, help="Poll interval in seconds")
    args = parser.parse_args()
    asyncio.run(align_abc(args.duration))


if __name__ == "__main__":
    main()
