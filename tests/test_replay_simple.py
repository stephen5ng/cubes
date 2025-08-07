#!/usr/bin/env python3

import json
import sys
import os

class GameReplayer:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.events = []
        self.current_event_index = 0
        self.start_time_ms = None
        self.replay_start_time_ms = None
        
    def load_events(self):
        """Load events from the log file."""
        with open(self.log_file, 'r') as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    self.events.append(event)
                    if event['event_type'] == 'game_start':
                        self.start_time_ms = event['data']['start_time_ms']
        
        # Sort events by timestamp
        self.events.sort(key=lambda x: x['timestamp_ms'])
        
    def start_replay(self, now_ms: int):
        """Start replay at the given time."""
        self.replay_start_time_ms = now_ms
        self.current_event_index = 0
        
    def get_next_events(self, now_ms: int):
        """Get all events that should be triggered at the current time."""
        if not self.replay_start_time_ms:
            return []
            
        current_time_ms = now_ms - self.replay_start_time_ms
        events_to_trigger = []
        
        while (self.current_event_index < len(self.events) and 
               self.events[self.current_event_index]['timestamp_ms'] <= current_time_ms):
            events_to_trigger.append(self.events[self.current_event_index])
            self.current_event_index += 1
            
        return events_to_trigger
        
    def is_replay_complete(self):
        """Check if replay is complete."""
        return self.current_event_index >= len(self.events)

def test_replay():
    """Test the replay functionality."""
    # Create a simple test file with sample events
    test_events = [
        {"timestamp_ms": 1000, "event_type": "game_start", "data": {"start_time_ms": 1000}},
        {"timestamp_ms": 1100, "event_type": "input_movement", "data": {"x": 10, "y": 20}},
        {"timestamp_ms": 1200, "event_type": "input_letter", "data": {"letter": "A"}},
        {"timestamp_ms": 1300, "event_type": "game_end", "data": {"score": 100}}
    ]
    
    # Write test events to a temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for event in test_events:
            f.write(json.dumps(event) + '\n')
        temp_file = f.name
    
    try:
        # Test loading events from the temporary file
        replayer = GameReplayer(temp_file)
        replayer.load_events()
        
        print(f"Loaded {len(replayer.events)} events")
        
        # Test getting events at different times
        replayer.start_replay(1000)  # Start at time 1000
        
        # At time 2000 (relative time 1000), should get game_start
        events = replayer.get_next_events(2000)
        print(f"At time 2000, got {len(events)} events")
        assert len(events) == 1
        assert events[0]['event_type'] == 'game_start'
        
        # At time 2100 (relative time 1100), should get input_movement
        events = replayer.get_next_events(2100)
        print(f"At time 2100, got {len(events)} events")
        assert len(events) == 1
        assert events[0]['event_type'] == 'input_movement'
        
        # At time 2200 (relative time 1200), should get input_letter
        events = replayer.get_next_events(2200)
        print(f"At time 2200, got {len(events)} events")
        assert len(events) == 1
        assert events[0]['event_type'] == 'input_letter'
        
        # At time 2300 (relative time 1300), should get game_end
        events = replayer.get_next_events(2300)
        print(f"At time 2300, got {len(events)} events")
        for event in events:
            print(f"  Event: {event['event_type']} at {event['timestamp_ms']}")
        assert len(events) == 1  # Only the game_end event
        
        # Check if replay is complete
        assert replayer.is_replay_complete()
        
        print("Replay test passed!")
    finally:
        # Clean up temporary file
        os.unlink(temp_file)

if __name__ == "__main__":
    test_replay() 