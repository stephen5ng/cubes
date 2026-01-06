"""Game replayer for testing and debugging."""

import json


class GameReplayer:
    """Loads and replays game events from log files."""

    def __init__(self, log_file: str):
        self.log_file = log_file
        self.events = []

    def load_events(self):
        """Load events from the log file, skipping metadata."""
        if not self.log_file:
            return

        with open(self.log_file, 'r') as f:
            lines = f.readlines()

        # Skip seed, delay_ms, and game_config metadata lines at the beginning
        while lines and lines[0].startswith('{"event_type": "'):
            first_event = json.loads(lines[0])
            if first_event.get("event_type") in ["seed", "delay_ms", "game_config"]:
                lines = lines[1:]
            else:
                break

        for line in lines:
            if line.strip():
                event = json.loads(line)
                self.events.append(event)

        self.events.reverse()
