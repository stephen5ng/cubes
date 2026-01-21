"""Game replayer for testing and debugging."""

import json


class GameReplayer:
    """Loads and replays game events from log files."""

    def __init__(self, log_file: str):
        self.log_file = log_file
        self.events = []
        # Metadata extracted from replay file
        self.seed = None
        self.delay_ms = None
        self.descent_mode = None
        self.timed_duration_s = None

    def load_events(self):
        """Load events from the log file, extracting metadata."""
        if not self.log_file:
            return

        with open(self.log_file, 'r') as f:
            lines = f.readlines()

        # Extract metadata from the beginning of the file
        while lines and lines[0].startswith('{"event_type": "'):
            first_event = json.loads(lines[0])
            event_type = first_event.get("event_type")
            if event_type == "seed":
                self.seed = first_event.get("seed")
                lines = lines[1:]
            elif event_type == "delay_ms":
                self.delay_ms = first_event.get("delay_ms")
                lines = lines[1:]
            elif event_type == "game_config":
                self.descent_mode = first_event.get("descent_mode")
                self.timed_duration_s = first_event.get("timed_duration_s")
                lines = lines[1:]
            else:
                break

        for line in lines:
            if line.strip():
                event = json.loads(line)
                self.events.append(event)

        self.events.reverse()

    def get_start_time(self) -> int:
        """Get the timestamp of the first event, or 0 if no events."""
        if not self.events:
            return 0
        # Events are stored in reverse order (stack), so last element is first event
        return self.events[-1].get('timestamp_ms', 0)
