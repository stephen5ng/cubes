"""Logging classes for game results, MQTT activity, and replay generation."""

import json

class BaseLogger:
    """Base class for all JSONL-based loggers."""
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.log_f = None
        
    def start_logging(self):
        """Open the log file for writing."""
        print(f"STARTING LOGGING {self.log_file}")
        if self.log_file:
            self.log_f = open(self.log_file, "w")
    
    def stop_logging(self):
        """Close the log file."""
        if self.log_f:
            self.log_f.close()
            self.log_f = None
    
    def _write_event(self, event: dict):
        """Write a dictionary as a JSON line to the log file."""
        if not self.log_f:
            return
        self.log_f.write(json.dumps(event) + "\n")
        self.log_f.flush()

class OutputLogger(BaseLogger):
    """Logs game-level events like word formation and letter movement."""
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
    """Logs system-level game events for replaying or debugging."""
    def log_seed(self, seed: int):
        event = {
            "event_type": "seed",
            "seed": seed
        }
        print(f">>>>>>>> logging seed {event}")
        self._write_event(event)

    def log_delay_ms(self, delay_ms: int):
        event = {
            "event_type": "delay_ms",
            "delay_ms": delay_ms
        }
        print(f">>>>>>>> logging delay_ms {event}")
        self._write_event(event)
        
    def log_events(self, now_ms: int, events: dict):
        log_entry = {
            "timestamp_ms": now_ms,
            "events": events
        }
        
        self._write_event(log_entry)

class PublishLogger(BaseLogger):
    """Logs MQTT publication activity."""
    def log_mqtt_publish(self, topic: str, message, retain: bool, timestamp_ms: int):
        """Log MQTT publish event to JSONL file."""
        event = {
            "time": timestamp_ms,
            "topic": topic,
            "message": message,
            "retain": retain
        }
        self._write_event(event)
