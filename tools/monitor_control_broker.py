#!/usr/bin/env python3
"""Monitor the control MQTT broker for game control messages.

This script subscribes to the control broker and displays final score messages.
Useful for testing and monitoring the game control system.

Usage:
    ./tools/monitor_control_broker.py

Environment Variables:
    MQTT_CONTROL_SERVER: Control broker hostname (default: localhost)
    MQTT_CONTROL_PORT: Control broker port (default: 1884)
"""

import asyncio
import json
import os
import sys
from datetime import datetime

try:
    import aiomqtt
except ImportError:
    print("Error: aiomqtt not installed. Run: pip install aiomqtt")
    sys.exit(1)


def format_score_message(payload: str) -> str:
    """Format a score message for display."""
    try:
        data = json.loads(payload)
        timestamp = datetime.now().strftime("%H:%M:%S")

        lines = [
            f"\n{'='*60}",
            f"[{timestamp}] FINAL SCORE RECEIVED",
            f"{'='*60}",
            f"  Score:        {data.get('score', 'N/A')}",
            f"  Stars:        {data.get('stars', 'N/A')}",
            f"  Exit Code:    {data.get('exit_code', 'N/A')} ({'Win' if data.get('exit_code') == 10 else 'Loss/Abort'})",
            f"  Min Win Score: {data.get('min_win_score', 'N/A')}",
            f"  Duration:     {data.get('duration_s', 0):.1f}s",
            f"{'='*60}\n",
        ]
        return "\n".join(lines)
    except json.JSONDecodeError:
        return f"[{datetime.now().strftime('%H:%M:%S')}] Invalid JSON: {payload}"


async def main():
    """Subscribe to control broker and monitor messages."""
    mqtt_server = os.environ.get("MQTT_CONTROL_SERVER", "localhost")
    mqtt_port = int(os.environ.get("MQTT_CONTROL_PORT", "1884"))

    print(f"Connecting to control broker at {mqtt_server}:{mqtt_port}")
    print("Subscribed to: game/final_score")
    print("Press Ctrl+C to exit\n")

    try:
        async with aiomqtt.Client(hostname=mqtt_server, port=mqtt_port) as client:
            await client.subscribe("game/final_score")

            async for message in client.messages:
                payload = message.payload.decode()
                print(format_score_message(payload))

    except aiomqtt.MqttError as e:
        print(f"\nError: Could not connect to MQTT broker at {mqtt_server}:{mqtt_port}")
        print(f"Details: {e}")
        print("\nMake sure the control broker is running:")
        print(f"  mosquitto -p {mqtt_port}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


if __name__ == "__main__":
    asyncio.run(main())
