#!/usr/bin/env python3
"""Run the Blockwords game with MQTT broker management and game_on mode support.

This script replaces runpygame.sh with Python implementation for better cross-platform
compatibility and maintainability.
"""

import argparse
import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
from typing import Optional

import aiomqtt

# Environment configuration
MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")
MQTT_CONTROL_SERVER = os.environ.get("MQTT_CONTROL_SERVER", "localhost")
MQTT_CONTROL_PORT = int(os.environ.get("MQTT_CONTROL_PORT", "1884"))

# Paths
VENV_PATH = "cube_env/bin/activate"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MOSQUITTO_PATH = "/opt/homebrew/opt/mosquitto/sbin/mosquitto"
DELETE_MQTT_SCRIPT = os.path.join(SCRIPT_DIR, "tools/delete_all_mqtt.sh")


def is_port_open(host: str, port: int) -> bool:
    """Check if a port is open on a host."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _calculate_level_params(level: int) -> tuple[int, int]:
    """Calculate min_win_score and descent_duration for a given level.

    For levels 0-2, values are predefined. For levels 3+:
    - min_win_score increases by 50% each level
    - descent_duration decreases by 1/3 each level

    Args:
        level: The level number

    Returns:
        Tuple of (min_win_score, descent_duration)
    """
    # Base level configurations
    level_configs = {
        0: (90, 90),
        1: (90, 180),
        2: (360, 120),
    }

    if level in level_configs:
        return level_configs[level]

    # For levels > 2, calculate from level 2
    min_win_score, descent_duration = level_configs[2]

    # Level 3 and above: progressive difficulty
    for _ in range(3, level + 1):
        min_win_score = int(min_win_score * 1.5)  # +50%
        descent_duration = int(descent_duration * 2 / 3)  # -1/3

    return min_win_score, descent_duration


def build_game_params(mode: str, level: int) -> str:
    """Build game parameters JSON based on mode and level.

    Args:
        mode: Game mode ("new", "game_on", or "classic")
        level: Level number (0+)

    Returns:
        JSON string with game parameters
    """
    if mode == "new":
        return json.dumps({
            "descent_mode": "timed",
            "descent_duration": 120
        })
    elif mode == "game_on":
        min_win_score, descent_duration = _calculate_level_params(level)

        params = {
            "descent_mode": "timed",
            "descent_duration": descent_duration,
            "min_win_score": min_win_score,
            "stars": True,
            "level": level
        }

        # Level 0 is one-round mode
        if level == 0:
            params["one_round"] = True

        return json.dumps(params)

    # Classic mode - no special params
    return ""


def build_python_args(mode: str, level: int, extra_args: list[str]) -> list[str]:
    """Build command-line arguments for the Python game process.

    Args:
        mode: Game mode
        level: Level number
        extra_args: Additional command-line arguments

    Returns:
        List of arguments to pass to main.py
    """
    args = extra_args.copy()

    if mode == "new":
        args.extend(["--descent-mode", "timed"])
    elif mode == "classic":
        args.append("--continuous")
    elif mode == "game_on":
        min_win_score, descent_duration = _calculate_level_params(level)
        args.extend([
            "--descent-mode", "timed",
            "--stars",
            "--level", str(level),
            "--min-win-score", str(min_win_score),
            "--descent-duration", str(descent_duration)
        ])

        if level == 0:
            args.append("--one-round")

    return args


async def monitor_game_on(
    mqtt_host: str,
    mqtt_port: int,
    python_proc: subprocess.Popen,
    initial_level: int,
) -> int:
    """Monitor MQTT for game/ready and game/final_score in game_on mode.

    Args:
        mqtt_host: MQTT broker host
        mqtt_port: MQTT broker port
        python_proc: Python game subprocess
        initial_level: Starting level

    Returns:
        Exit code (0 for normal exit, non-zero for errors)
    """
    level = initial_level
    exit_event = asyncio.Event()
    final_exit_code = [0]  # Use list to allow mutation in nested function
    message_queue = asyncio.Queue()

    async def watch_process():
        """Background task to monitor Python process and exit if it terminates."""
        while True:
            poll_result = python_proc.poll()
            if poll_result is not None:
                # Python process exited
                final_exit_code[0] = poll_result or 0
                print(f"Python game process exited with code: {final_exit_code[0]}")
                exit_event.set()
                return
            await asyncio.sleep(0.2)

    async def listen_messages(client: aiomqtt.Client):
        """Background task to listen for MQTT messages and put them in queue."""
        async for message in client.messages:
            await message_queue.put(message)

    async with aiomqtt.Client(mqtt_host, port=mqtt_port) as client:
        # Subscribe to both topics
        await client.subscribe("game/final_score")
        await client.subscribe("game/ready")

        # Start background tasks
        watcher_task = asyncio.create_task(watch_process())
        listener_task = asyncio.create_task(listen_messages(client))

        print("Press ESC to start the game...")

        # Main loop: wait for either a message or exit event
        while not exit_event.is_set():
            try:
                # Wait for message with timeout, allowing us to check exit_event
                message = await asyncio.wait_for(message_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                # Check if process exited
                if exit_event.is_set():
                    break
                continue

            topic = str(message.topic)

            if topic == "game/ready":
                # User pressed ESC, game is ready to start
                print("Game ready! Starting...")
                params = build_game_params("game_on", level)
                if params:
                    await client.publish("game/start", payload=params)
                else:
                    await client.publish("game/start", payload="")

            elif topic == "game/final_score":
                try:
                    payload = message.payload.decode() if message.payload else ""
                    score_data = json.loads(payload) if payload else {}
                    exit_code = score_data.get("exit_code", 0)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                # Display final score
                print()
                print("=" * 42)
                print("           FINAL SCORE")
                print("=" * 42)

                if score_data:
                    print(f"  Score:        {score_data.get('score', 'N/A')}")
                    print(f"  Stars:        {score_data.get('stars', 'N/A')}")
                    result = "Win" if exit_code == 10 else ("Loss" if exit_code == 11 else "Quit/Abort")
                    print(f"  Result:       {result} (exit code: {exit_code})")
                    duration = score_data.get("duration_s", 0)
                    print(f"  Duration:     {duration:.1f}s")
                    min_win = score_data.get("min_win_score", 0)
                    if min_win > 0:
                        print(f"  Win Target:   {min_win}")

                print("=" * 42)
                print()

                # Handle win/loss/exit
                if exit_code == 10:
                    # Win - Advance Level
                    print("Win! Advancing level...")
                    level += 1
                    min_win_score, descent_duration = _calculate_level_params(level)
                    print(f"Current Level: {level} (target: {min_win_score}, duration: {descent_duration}s)")
                    print("Press ESC to continue...")
                elif exit_code == 11:
                    # Loss - Reset to Level 0
                    print("Sorry! Back to Level 0...")
                    level = 0
                    min_win_score, descent_duration = _calculate_level_params(level)
                    print(f"Reset to Level {level} (target: {min_win_score}, duration: {descent_duration}s)")
                    print("Press ESC to try again...")
                elif exit_code == 0:
                    # Normal exit - user quit
                    print("Game exited normally.")
                    exit_event.set()
                    break
                else:
                    # Error or other exit
                    print(f"Game exited with code: {exit_code}")
                    exit_event.set()
                    break

        # Clean up tasks
        watcher_task.cancel()
        listener_task.cancel()
        try:
            await watcher_task
        except asyncio.CancelledError:
            pass
        try:
            await listener_task
        except asyncio.CancelledError:
            pass

    return final_exit_code[0]


async def run_game_on(level: int, python_args: list[str]) -> int:
    """Run the game in game_on mode with MQTT monitoring.

    Args:
        level: Starting level
        python_args: Arguments to pass to main.py

    Returns:
        Exit code from the game
    """
    min_win_score, descent_duration = _calculate_level_params(level)
    print(f"Starting game_on mode at level: {level}")
    print(f"Level parameters: min_win_score={min_win_score}, descent_duration={descent_duration}s")
    print(f"Running game with arguments: {' '.join(python_args)}")

    # Start the Python game process
    # Use 'python3' which will resolve to venv python if PATH is set correctly
    python_exe = shutil.which("python3") or "python3"
    python_proc = subprocess.Popen(
        [python_exe, "./main.py"] + python_args,
        cwd=SCRIPT_DIR,
    )

    # Give Python a moment to start
    await asyncio.sleep(1)

    # Check if Python started successfully
    if python_proc.poll() is not None:
        print("ERROR: Python process failed to start")
        return python_proc.returncode or 1

    print(f"Python game started (PID: {python_proc.pid})")

    try:
        # Monitor MQTT and wait for game completion
        exit_code = await monitor_game_on(
            MQTT_CONTROL_SERVER,
            MQTT_CONTROL_PORT,
            python_proc,
            level,
        )
        return exit_code
    finally:
        # Clean up Python process
        if python_proc.poll() is None:
            python_proc.terminate()
            try:
                python_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                python_proc.kill()
                python_proc.wait()


def run_simple(python_args: list[str]) -> int:
    """Run the game in simple mode (classic or new) without MQTT monitoring.

    Args:
        python_args: Arguments to pass to main.py

    Returns:
        Exit code from the game
    """
    print(f"Running game with arguments: {' '.join(python_args)}")

    # Use 'python3' which will resolve to venv python if PATH is set correctly
    python_exe = shutil.which("python3") or "python3"
    proc = subprocess.Popen(
        [python_exe, "./main.py"] + python_args,
        cwd=SCRIPT_DIR,
    )

    return proc.wait()


def setup_environment():
    """Set up the Python environment."""
    # Add to PYTHONPATH
    pythonpath_parts = [
        os.path.join(SCRIPT_DIR, "src"),
        os.path.join(SCRIPT_DIR, "../easing-functions"),
        os.path.join(SCRIPT_DIR, "../rpi-rgb-led-matrix/bindings/python"),
    ]
    current_path = os.environ.get("PYTHONPATH", "")
    new_path = ":".join(pythonpath_parts)
    os.environ["PYTHONPATH"] = f"{new_path}:{current_path}" if current_path else new_path

    # Activate virtual environment (by modifying PATH)
    venv_bin = os.path.join(SCRIPT_DIR, "cube_env/bin")
    if os.path.isdir(venv_bin):
        os.environ["PATH"] = f"{venv_bin}:{os.environ.get('PATH', '')}"
        os.environ["VIRTUAL_ENV"] = os.path.join(SCRIPT_DIR, "cube_env")


async def async_main(mode: str, level: int, extra_args: list[str]) -> int:
    """Async main function that manages mosquitto processes and runs the game.

    Args:
        mode: Game mode
        level: Starting level
        extra_args: Additional command-line arguments

    Returns:
        Exit code
    """
    mosquitto_gameplay_proc = None
    mosquitto_control_proc = None
    python_exit_code = 0

    def cleanup_mosquitto():
        """Clean up mosquitto processes."""
        for proc in [mosquitto_gameplay_proc, mosquitto_control_proc]:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

    # Start gameplay broker (port 1883) if needed
    if not is_port_open(MQTT_SERVER, 1883):
        mosquitto_gameplay_proc = subprocess.Popen(
            [MOSQUITTO_PATH, "-p", "1883"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(0.5)

    # Start control broker (port 1884) if needed
    if not is_port_open(MQTT_CONTROL_SERVER, MQTT_CONTROL_PORT):
        mosquitto_control_proc = subprocess.Popen(
            [MOSQUITTO_PATH, "-p", str(MQTT_CONTROL_PORT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(0.5)

    # Delete all MQTT messages
    subprocess.run(
        ["bash", DELETE_MQTT_SCRIPT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Run the game
        if mode == "game_on":
            python_args = build_python_args(mode, level, extra_args)
            python_exit_code = await run_game_on(level, python_args)
        else:
            python_args = build_python_args(mode, level, extra_args)
            python_exit_code = run_simple(python_args)
    finally:
        cleanup_mosquitto()

    return python_exit_code


async def run_replay(replay_file: str, extra_args: list[str]) -> int:
    """Run the game in replay mode with MQTT broker setup.

    Args:
        replay_file: Path to the replay JSONL file
        extra_args: Additional arguments to pass to main.py

    Returns:
        Exit code from the game
    """
    print(f"Running replay: {replay_file}")
    mosquitto_gameplay_proc = None
    mosquitto_control_proc = None

    def cleanup_mosquitto():
        """Clean up mosquitto processes."""
        for proc in [mosquitto_gameplay_proc, mosquitto_control_proc]:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

    # Start gameplay broker (port 1883) if needed
    if not is_port_open(MQTT_SERVER, 1883):
        mosquitto_gameplay_proc = subprocess.Popen(
            [MOSQUITTO_PATH, "-p", "1883"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(0.5)

    # Start control broker (port 1884) if needed
    if not is_port_open(MQTT_CONTROL_SERVER, MQTT_CONTROL_PORT):
        mosquitto_control_proc = subprocess.Popen(
            [MOSQUITTO_PATH, "-p", str(MQTT_CONTROL_PORT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(0.5)

    # Delete all MQTT messages
    subprocess.run(
        ["bash", DELETE_MQTT_SCRIPT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Use 'python3' which will resolve to venv python if PATH is set correctly
        python_exe = shutil.which("python3") or "python3"
        proc = subprocess.Popen(
            [python_exe, "./main.py", "--replay", replay_file] + extra_args,
            cwd=SCRIPT_DIR,
        )
        return proc.wait()
    finally:
        cleanup_mosquitto()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Blockwords game with MQTT broker management"
    )
    parser.add_argument(
        "--mode",
        choices=["classic", "new", "game_on"],
        default="classic",
        help="Game mode (default: classic)",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=0,
        help="Level for game_on mode (0+, default: 0)",
    )
    parser.add_argument(
        "--replay",
        type=str,
        help="Replay a game from a log file (skips MQTT broker setup)",
    )
    parser.add_argument(
        "--descent-mode",
        type=str,
        default=None,
        help="Descent mode for replay (discrete or timed)",
    )
    parser.add_argument(
        "--descent-duration",
        type=int,
        default=None,
        help="Descent duration in seconds for replay",
    )
    parser.add_argument(
        "extra_args",
        nargs=argparse.REMAINDER,
        help="Extra arguments to pass to main.py",
    )

    args = parser.parse_args()

    # Set up environment
    setup_environment()

    # Build extra args from descent-mode/duration if specified
    replay_extra_args = args.extra_args.copy()
    if args.descent_mode:
        replay_extra_args.extend(["--descent-mode", args.descent_mode])
    if args.descent_duration is not None:
        replay_extra_args.extend(["--descent-duration", str(args.descent_duration)])

    # Handle replay mode (with MQTT broker setup)
    if args.replay:
        exit_code = asyncio.run(run_replay(args.replay, replay_extra_args))
        sys.exit(exit_code)

    # Run the async main with MQTT broker management
    exit_code = asyncio.run(async_main(args.mode, args.level, args.extra_args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
