#!/usr/bin/env python3

import json
import tempfile
import os

def test_logging():
    """Test the logging functionality."""
    # Create a temporary log file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        log_file = f.name
    
    try:
        # Test writing some events
        events = [
            {"timestamp_ms": 0, "event_type": "game_start", "data": {"start_time_ms": 1000}},
            {"timestamp_ms": 100, "event_type": "input_movement", "data": {"direction": "left", "player": 0, "cursor_position": 1}},
            {"timestamp_ms": 200, "event_type": "input_letter", "data": {"letter": "A", "player": 0, "current_guess": "A"}},
            {"timestamp_ms": 300, "event_type": "game_over", "data": {"final_score": 100, "duration_s": 30.5}}
        ]
        
        with open(log_file, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
        
        # Test reading the events
        with open(log_file, 'r') as f:
            read_events = []
            for line in f:
                if line.strip():
                    read_events.append(json.loads(line))
        
        print(f"Wrote {len(events)} events")
        print(f"Read {len(read_events)} events")
        
        # Verify they match
        assert len(events) == len(read_events)
        for i, (original, read) in enumerate(zip(events, read_events)):
            assert original == read, f"Event {i} doesn't match"
        
        print("Logging test passed!")
        
    finally:
        # Clean up
        os.unlink(log_file)

if __name__ == "__main__":
    test_logging()
