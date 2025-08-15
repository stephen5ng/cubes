"""Latency metrics logging system for BlockWords cubes game.

This module provides comprehensive latency measurement and logging capabilities
for debugging performance issues across the game server and ESP32 cubes.
"""

import json
import time
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass
import os


@dataclass
class LatencyOperation:
    """Represents an ongoing latency measurement operation."""
    operation_id: str
    operation_type: str
    start_time: float
    metadata: Dict[str, Any]


class LatencyLogger:
    """High-performance latency logger with JSONL output.
    
    Designed to measure latency across the complete game pipeline:
    - Game server event processing
    - MQTT publish/receive timing
    - Input device response times
    - ESP32 communication delays
    """
    
    def __init__(self, log_file: str, enabled: bool):
        """Initialize the latency logger."""
        self.log_file = log_file
        self.enabled = enabled
        self._active_operations: Dict[str, LatencyOperation] = {}
        
        if self.enabled:
            print(f"LatencyLogger enabled, logging to: {self.log_file}")
        
    def start_operation(self, operation_type: str) -> str:
        """Start timing a latency-sensitive operation."""
        if not self.enabled:
            return ""
            
        token = str(uuid.uuid4())
        start_time = time.perf_counter()
        
        self._active_operations[token] = LatencyOperation(
            token,
            operation_type,
            start_time,
            {}
        )
        
        return token
        
    def end_operation(self, token: str, success: bool) -> None:
        """Complete timing of an operation and log the result."""
        if not self.enabled or not token or token not in self._active_operations:
            return
            
        operation = self._active_operations.pop(token)
        end_time = time.perf_counter()
        duration_ms = (end_time - operation.start_time) * 1000
        
        metadata = operation.metadata.copy()
        metadata['success'] = success
        
        self._write_log_entry(
            operation.operation_type,
            operation.operation_id,
            duration_ms,
            metadata
        )
    
    def log_mqtt_publish(self, topic: str, payload_size: int, duration_ms: float, 
                        success: bool) -> None:
        """Log MQTT publish latency."""
        if not self.enabled:
            return
            
        full_metadata = {
            'topic': topic,
            'payload_size': payload_size,
            'success': success
        }
        
        self._write_log_entry(
            'mqtt_publish',
            f"mqtt_{topic}_{int(time.time()*1000)}",
            duration_ms,
            full_metadata
        )
    
    def log_event_processing(self, event_type: str, duration_ms: float) -> None:
        """Log event processing latency."""
        if not self.enabled:
            return
            
        full_metadata = {
            'event_type': event_type
        }
        
        self._write_log_entry(
            'event_processing',
            f"event_{event_type}_{int(time.time()*1000)}",
            duration_ms,
            full_metadata
        )
    
    def log_input_latency(self, input_type: str, device: str, latency_ms: float) -> None:
        """Log input device latency."""
        if not self.enabled:
            return
            
        full_metadata = {
            'input_type': input_type,
            'device': device
        }
        
        self._write_log_entry(
            'input_latency',
            f"input_{input_type}_{device}_{int(time.time()*1000)}",
            latency_ms,
            full_metadata
        )
    
    def log_roundtrip_latency(self, source: str, destination: str, duration_ms: float, 
                            message_type: str) -> None:
        """Log end-to-end roundtrip latency."""
        if not self.enabled:
            return
            
        full_metadata = {
            'source': source,
            'destination': destination,
            'message_type': message_type
        }
        
        self._write_log_entry(
            'roundtrip_latency',
            f"roundtrip_{source}_{destination}_{int(time.time()*1000)}",
            duration_ms,
            full_metadata
        )
    
    def _write_log_entry(self, operation_type: str, operation_id: str, 
                        duration_ms: float, metadata: Dict[str, Any]) -> None:
        """Write a latency measurement to the log file."""
        log_entry = {
            'timestamp_ms': int(time.time() * 1000),
            'operation_type': operation_type,
            'operation_id': operation_id,
            'duration_ms': round(duration_ms, 3),
            'metadata': metadata
        }
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"LatencyLogger write error: {e}")
    
    def get_active_operations(self) -> Dict[str, str]:
        """Get currently active operations (for debugging)."""
        return {token: op.operation_type for token, op in self._active_operations.items()}
    
    def clear_active_operations(self) -> None:
        """Clear all active operations (for cleanup)."""
        self._active_operations.clear()


# Global instance for convenient access
latency_logger = LatencyLogger(
    log_file="latency_metrics.jsonl",
    enabled=os.getenv('LATENCY_LOGGING_ENABLED', 'false').lower() == 'true'
)