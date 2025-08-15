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


def _build_group_maps(cubes: List[str], tags: List[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return (cube->tag, tag->cube) maps for a group. Ignores extra '-' tag."""
    cubes_only_tags = tags[:len(cubes)]
    cube_to_tag = {cube: tag for cube, tag in zip(cubes, cubes_only_tags)}
    tag_to_cube = {tag: cube for cube, tag in cube_to_tag.items()}
    return cube_to_tag, tag_to_cube


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
    all_cube_ids = get_lines("cube_ids.txt")
    # tag_ids no longer used for control path; keep for compatibility if present
    all_tag_ids = get_lines("tag_ids.txt") if os.path.exists("tag_ids.txt") else []

    p0_cubes = all_cube_ids[:6]
    p1_cubes = all_cube_ids[6:]
    p0_tags = all_tag_ids[:6] if all_tag_ids else []
    p1_tags = all_tag_ids[6:] if all_tag_ids else []
    print(f"p0_cubes {p0_cubes}")

    # Allow publishing neighbor tags; '-' can exist but is not mapped
    p0_cube_to_tag, _ = _build_group_maps(p0_cubes, p0_tags)
    p1_cube_to_tag, _ = _build_group_maps(p1_cubes, p1_tags)
    wait_for_scramble = False
    async with aiomqtt.Client(MQTT_SERVER) as client:
        cube_to_letter: Dict[str, str] = {}
        consumer_task = asyncio.create_task(_start_letter_consumer(client, cube_to_letter))
        try:
            while True:
                # Process each group independently
                for group_cubes, cube_to_tag in (
                    (p0_cubes, p0_cube_to_tag),
                    (p1_cubes, p1_cube_to_tag),
                ):
                    if not group_cubes:
                        continue
                    letters = {cube_to_letter.get(c, "") for c in group_cubes}
                    letters.discard("")
                    letters.discard(" ")
                    # print(f"group_cubes {group_cubes} letters: {letters}")
                    if not letters:
                        continue
                    # Allow spaces in addition to A/B/C
                    if letters.issubset({"A", "B", "C"}) and {"A", "B", "C"}.issubset(letters):
                        # Map letters to cubes and publish neighbor tags
                        cubes_by_letter = {cube_to_letter.get(c, ""): c for c in group_cubes if cube_to_letter.get(c)}
                        cube_a = cubes_by_letter.get("A")
                        cube_b = cubes_by_letter.get("B")
                        cube_c = cubes_by_letter.get("C")
                        if not wait_for_scramble and cube_a and cube_b and cube_c:
                            print("start_game STARTING GAME")
                            wait_for_scramble = True
                            # Publish direct neighbor cubes on new protocol
                            await client.publish(f"cube/right/{cube_a}", payload=cube_b)
                            await client.publish(f"cube/right/{cube_b}", payload=cube_c)
                    else:
                        wait_for_scramble = False
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
