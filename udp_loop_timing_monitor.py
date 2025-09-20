#!/usr/bin/env python3
"""
UDP Loop Timing Monitor

Listens for UDP messages on port 54322 containing cube loop timing data.
Messages are in format "CUBE_ID:loop_time_ms" and are logged to a file.

Usage:
    python udp_loop_timing_monitor.py [--port PORT] [--output OUTPUT]
"""

import socket
import time
import json
import argparse
from datetime import datetime
import threading

class UDPLoopTimingMonitor:
    def __init__(self, port=54322, output_file="cube_loop_timing.jsonl"):
        self.port = port
        self.output_file = output_file
        self.running = True
        self.socket = None
        
    def start_monitoring(self):
        """Start monitoring UDP messages for loop timing data"""
        print(f"🔍 Starting UDP loop timing monitor")
        print(f"📊 Listening on port {self.port}")
        print(f"📝 Output file: {self.output_file}")
        print(f"📡 Expected message format: CUBE_ID:loop_time_ms")
        print()
        
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('', self.port))
            self.socket.settimeout(1.0)  # 1 second timeout for clean shutdown
            
            print(f"✅ UDP server listening on port {self.port}")
            print("Press Ctrl+C to stop monitoring")
            print("-" * 50)
            
            with open(self.output_file, 'w') as f:
                message_count = 0
                
                while self.running:
                    try:
                        data, addr = self.socket.recvfrom(1024)
                        message = data.decode('utf-8')
                        receive_time = time.time()
                        message_count += 1
                        
                        # Parse message format: "CUBE_ID:loop_time_ms"
                        if ':' in message:
                            cube_id, loop_time_str = message.split(':', 1)
                            try:
                                loop_time_ms = int(loop_time_str)
                                
                                # Create log entry
                                log_entry = {
                                    'timestamp': datetime.fromtimestamp(receive_time).isoformat(),
                                    'receive_time': receive_time,
                                    'cube_id': cube_id,
                                    'loop_time_ms': loop_time_ms,
                                    'source_ip': addr[0],
                                    'source_port': addr[1],
                                    'message_number': message_count
                                }
                                
                                # Write to JSONL file
                                f.write(json.dumps(log_entry) + '\n')
                                f.flush()
                                
                                # Print to console
                                print(f"[{message_count:4d}] Cube {cube_id}: {loop_time_ms}ms (from {addr[0]})")
                                
                            except ValueError:
                                print(f"⚠️  Invalid loop time format: {message} from {addr[0]}")
                        else:
                            print(f"⚠️  Invalid message format: {message} from {addr[0]}")
                            
                    except socket.timeout:
                        # Timeout is normal, continue loop
                        continue
                    except Exception as e:
                        if self.running:  # Only log errors if we're still supposed to be running
                            print(f"❌ Error receiving UDP message: {e}")
                        
        except KeyboardInterrupt:
            print(f"\n⏹️  Monitoring stopped by user")
        except Exception as e:
            print(f"❌ Error setting up UDP server: {e}")
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        print(f"\n💾 Loop timing data saved to: {self.output_file}")
        
    def print_summary(self):
        """Print summary of collected data"""
        try:
            with open(self.output_file, 'r') as f:
                entries = [json.loads(line) for line in f if line.strip()]
                
            if not entries:
                print("No timing data collected")
                return
                
            print(f"\n📊 SUMMARY")
            print("=" * 50)
            print(f"Total messages: {len(entries)}")
            
            # Group by cube
            cube_stats = {}
            for entry in entries:
                cube_id = entry['cube_id']
                loop_time = entry['loop_time_ms']
                
                if cube_id not in cube_stats:
                    cube_stats[cube_id] = []
                cube_stats[cube_id].append(loop_time)
            
            # Print per-cube statistics
            for cube_id in sorted(cube_stats.keys()):
                times = cube_stats[cube_id]
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                
                print(f"Cube {cube_id}: {len(times)} samples - "
                      f"avg: {avg_time:.1f}ms, min: {min_time}ms, max: {max_time}ms")
                      
        except Exception as e:
            print(f"❌ Error generating summary: {e}")

def main():
    parser = argparse.ArgumentParser(description="Monitor cube loop timing via UDP")
    parser.add_argument("--port", type=int, default=54322, help="UDP port to listen on")
    parser.add_argument("--output", default="cube_loop_timing.jsonl", help="Output JSONL file")
    
    args = parser.parse_args()
    
    monitor = UDPLoopTimingMonitor(port=args.port, output_file=args.output)
    
    try:
        monitor.start_monitoring()
    finally:
        monitor.print_summary()

if __name__ == "__main__":
    main()