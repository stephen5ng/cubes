#!/usr/bin/env python3

"""Analyze end-to-end latency by correlating game server logs and ESP32 serial output."""

import json
import re
import argparse
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import statistics


@dataclass
class LatencyMeasurement:
    correlation_id: str
    game_server_timestamp: int
    esp32_timestamp: int
    cube_id: str
    letter: str
    latency_ms: float


def parse_latency_log(log_file: str) -> Dict[str, Tuple[int, str, str]]:
    """Parse latency_metrics.jsonl to find end-to-end operation starts.
    
    Returns:
        Dict mapping correlation_id to (timestamp_ms, cube_id, letter)
    """
    correlations = {}
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                    
                try:
                    entry = json.loads(line)
                    if (entry.get('operation_type') == 'roundtrip_latency' and 
                        entry.get('metadata', {}).get('message_type', '').startswith('letter_start_')):
                        
                        # Extract correlation ID and letter from message_type
                        message_type = entry['metadata']['message_type']
                        # Format: letter_start_{correlation_id}_{letter}
                        parts = message_type.split('_')
                        if len(parts) >= 4:
                            correlation_id = parts[2]
                            letter = parts[3] if len(parts) > 3 else '?'
                            cube_id = entry['metadata'].get('destination', 'unknown')
                            timestamp = entry['timestamp_ms']
                            
                            correlations[correlation_id] = (timestamp, cube_id, letter)
                            
                except json.JSONDecodeError:
                    continue
                    
    except FileNotFoundError:
        print(f"Warning: Latency log file {log_file} not found")
        
    return correlations


def parse_esp32_serial(serial_file: str) -> Dict[str, Tuple[int, str]]:
    """Parse ESP32 serial output to find display buffer flips.
    
    Returns:
        Dict mapping correlation_id to (timestamp_ms, cube_id)
    """
    display_completions = {}
    
    # Pattern for ESP32 display buffer flip logs
    flip_pattern = r'\[(\d+)\] DISPLAY_BUFFER_FLIP - correlation_id: ([a-zA-Z0-9\-]+)'
    
    try:
        with open(serial_file, 'r') as f:
            for line in f:
                match = re.search(flip_pattern, line)
                if match:
                    esp32_timestamp = int(match.group(1))
                    correlation_id = match.group(2)
                    display_completions[correlation_id] = (esp32_timestamp, "unknown")
                    print(f"Debug: Found ESP32 completion - {correlation_id} at {esp32_timestamp}")
                    
    except FileNotFoundError:
        print(f"Warning: ESP32 serial file {serial_file} not found")
        
    return display_completions


def correlate_measurements(game_starts: Dict[str, Tuple[int, str, str]], 
                          esp32_completions: Dict[str, Tuple[int, str]]) -> List[LatencyMeasurement]:
    """Correlate game server starts with ESP32 completions to calculate latency."""
    measurements = []
    
    for correlation_id, (game_timestamp, cube_id, letter) in game_starts.items():
        if correlation_id in esp32_completions:
            esp32_timestamp, _ = esp32_completions[correlation_id]
            
            # Convert ESP32 millis() to same time base as game server
            # This is approximate - real implementation would need time sync
            latency_ms = abs(esp32_timestamp - (game_timestamp % (2**32)))
            
            # Filter out unreasonable measurements (likely clock sync issues)
            if 0 < latency_ms < 10000:  # Between 0 and 10 seconds
                measurements.append(LatencyMeasurement(
                    correlation_id=correlation_id,
                    game_server_timestamp=game_timestamp,
                    esp32_timestamp=esp32_timestamp,
                    cube_id=cube_id,
                    letter=letter,
                    latency_ms=latency_ms
                ))
    
    return measurements


def analyze_latency(measurements: List[LatencyMeasurement]) -> None:
    """Analyze and report latency statistics."""
    if not measurements:
        print("No correlated measurements found")
        return
        
    latencies = [m.latency_ms for m in measurements]
    
    print(f"\n=== End-to-End Latency Analysis ===")
    print(f"Total measurements: {len(measurements)}")
    print(f"Average latency: {statistics.mean(latencies):.1f} ms")
    print(f"Median latency: {statistics.median(latencies):.1f} ms")
    print(f"Min latency: {min(latencies):.1f} ms")
    print(f"Max latency: {max(latencies):.1f} ms")
    
    if len(latencies) > 1:
        print(f"Standard deviation: {statistics.stdev(latencies):.1f} ms")
        
    # Show worst performers
    worst = sorted(measurements, key=lambda m: m.latency_ms, reverse=True)[:5]
    print(f"\n=== Slowest Measurements ===")
    for i, m in enumerate(worst, 1):
        print(f"{i}. {m.latency_ms:.1f}ms - Cube {m.cube_id} letter '{m.letter}' ({m.correlation_id[:8]})")
        
    # Show distribution
    ranges = [
        (0, 50, "Excellent"),
        (50, 100, "Good"), 
        (100, 200, "Fair"),
        (200, 500, "Poor"),
        (500, float('inf'), "Unacceptable")
    ]
    
    print(f"\n=== Latency Distribution ===")
    for min_lat, max_lat, label in ranges:
        count = sum(1 for lat in latencies if min_lat <= lat < max_lat)
        if count > 0:
            percentage = (count / len(latencies)) * 100
            print(f"{label} ({min_lat}-{max_lat if max_lat != float('inf') else '∞'}ms): {count} ({percentage:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description='Analyze end-to-end cube display latency')
    parser.add_argument('--latency-log', default='latency_metrics.jsonl',
                       help='Game server latency log file')
    parser.add_argument('--esp32-serial', required=True,
                       help='ESP32 serial output file')
    parser.add_argument('--output', help='Output CSV file for detailed results')
    
    args = parser.parse_args()
    
    print("Parsing game server latency logs...")
    game_starts = parse_latency_log(args.latency_log)
    
    print("Parsing ESP32 serial output...")
    esp32_completions = parse_esp32_serial(args.esp32_serial)
    
    print(f"Found {len(game_starts)} game server starts")
    print(f"Found {len(esp32_completions)} ESP32 completions")
    
    print("Correlating measurements...")
    measurements = correlate_measurements(game_starts, esp32_completions)
    
    analyze_latency(measurements)
    
    if args.output and measurements:
        with open(args.output, 'w') as f:
            f.write("correlation_id,game_timestamp,esp32_timestamp,cube_id,letter,latency_ms\n")
            for m in measurements:
                f.write(f"{m.correlation_id},{m.game_server_timestamp},{m.esp32_timestamp},"
                       f"{m.cube_id},{m.letter},{m.latency_ms:.1f}\n")
        print(f"\nDetailed results written to {args.output}")


if __name__ == "__main__":
    main()