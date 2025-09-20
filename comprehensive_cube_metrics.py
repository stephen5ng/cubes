#!/usr/bin/env python3
"""
Comprehensive Cube Metrics Monitor

Measures and records three types of timing data for ESP32 cubes:
1. Loop execution times (via UDP "timing" command)
2. MQTT ping response times (via MQTT ping/echo)
3. UDP ping response times (via UDP "ping"/"pong")

All data is saved to a single JSONL file with consistent formatting.

Usage:
    python comprehensive_cube_metrics.py [--cubes CUBE_IDS] [--duration SECONDS] [--output FILE]
"""

import asyncio
import aiomqtt
import socket
import time
import json
import argparse
from datetime import datetime
import sys

class CubeMetricsMonitor:
    def __init__(self, cube_ids=[1, 6], output_file="cube_metrics.jsonl", mqtt_broker="192.168.8.247"):
        self.cube_ids = cube_ids
        self.output_file = output_file
        self.mqtt_broker = mqtt_broker
        self.results = []
        self.sample_counter = 0
        
        # Cube IP mapping (from update.sh logic)
        self.cube_ips = {cube_id: f"192.168.8.{20 + cube_id}" for cube_id in cube_ids}
        
    async def run_monitoring(self, duration_seconds=60, interval_seconds=3):
        """Run comprehensive monitoring for specified duration"""
        print(f"🔍 Comprehensive Cube Metrics Monitor")
        print(f"📊 Monitoring cubes: {self.cube_ids}")
        print(f"⏱️  Duration: {duration_seconds}s, Interval: {interval_seconds}s")
        print(f"📡 MQTT broker: {self.mqtt_broker}")
        print(f"💾 Output file: {self.output_file}")
        print()
        
        # Clear output file
        with open(self.output_file, 'w') as f:
            pass
        
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration_seconds:
                elapsed = int(time.time() - start_time)
                print(f"[{elapsed:3d}s] Starting measurement round...")
                
                # Measure all metrics for all cubes
                await self._measure_all_metrics()
                
                # Wait for next interval
                print(f"      Waiting {interval_seconds}s for next round...")
                await asyncio.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")
        
        # Display summary
        self._print_summary()
        
    async def _measure_all_metrics(self):
        """Measure all three metrics for all cubes"""
        measurement_time = time.time()
        
        # Create tasks for concurrent measurement
        tasks = []
        for cube_id in self.cube_ids:
            tasks.append(self._measure_cube_metrics(cube_id, measurement_time))
        
        # Wait for all measurements to complete
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _measure_cube_metrics(self, cube_id, measurement_time):
        """Measure all metrics for a single cube"""
        cube_ip = self.cube_ips[cube_id]
        
        # Measure UDP ping time
        udp_ping_ms = await self._measure_udp_ping(cube_ip)
        
        # Measure loop time
        loop_time_ms = await self._measure_loop_time(cube_ip)
        
        # Measure MQTT ping time
        mqtt_ping_ms = await self._measure_mqtt_ping(cube_id)
        
        # Create comprehensive log entry
        self.sample_counter += 1
        log_entry = {
            'timestamp': datetime.fromtimestamp(measurement_time).isoformat(),
            'measurement_time': measurement_time,
            'cube_id': cube_id,
            'cube_ip': cube_ip,
            'sample_number': self.sample_counter,
            'metrics': {
                'udp_ping_ms': udp_ping_ms,
                'loop_time_ms': loop_time_ms,
                'mqtt_ping_ms': mqtt_ping_ms
            },
            'measurement_success': {
                'udp_ping': udp_ping_ms is not None,
                'loop_time': loop_time_ms is not None,
                'mqtt_ping': mqtt_ping_ms is not None
            }
        }
        
        self.results.append(log_entry)
        
        # Save to file immediately
        with open(self.output_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        # Print results
        udp_str = f"{udp_ping_ms:.1f}ms" if udp_ping_ms is not None else "FAIL"
        loop_str = f"{loop_time_ms}ms" if loop_time_ms is not None else "FAIL"
        mqtt_str = f"{mqtt_ping_ms:.1f}ms" if mqtt_ping_ms is not None else "FAIL"
        
        print(f"      Cube {cube_id}: UDP={udp_str}, Loop={loop_str}, MQTT={mqtt_str}")
    
    async def _measure_udp_ping(self, cube_ip, timeout=2):
        """Measure UDP ping time using ping/pong protocol"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            
            start_time = time.time()
            sock.sendto(b'ping', (cube_ip, 54321))
            data, addr = sock.recvfrom(1024)
            end_time = time.time()
            
            sock.close()
            
            if data.decode() == 'pong':
                return (end_time - start_time) * 1000  # Convert to ms
            else:
                return None
                
        except Exception:
            return None
    
    async def _measure_loop_time(self, cube_ip, timeout=2):
        """Measure loop execution time using timing command"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            
            sock.sendto(b'timing', (cube_ip, 54321))
            data, addr = sock.recvfrom(1024)
            
            sock.close()
            
            response = data.decode()
            if ':' in response:
                _, loop_time_str = response.split(':', 1)
                return int(loop_time_str)
            else:
                return None
                
        except Exception:
            return None
    
    async def _measure_mqtt_ping(self, cube_id, timeout=3):
        """Measure MQTT ping time using ping/echo protocol"""
        try:
            ping_topic = f"cube/{cube_id}/ping"
            echo_topic = f"cube/{cube_id}/echo"
            
            # Generate unique ping ID
            ping_id = f"ping_{cube_id}_{int(time.time() * 1000)}"
            
            async with aiomqtt.Client(self.mqtt_broker) as client:
                # Subscribe to echo topic
                await client.subscribe(echo_topic)
                
                # Send ping
                start_time = time.time()
                await client.publish(ping_topic, ping_id)
                
                # Wait for response with timeout
                async with asyncio.timeout(timeout):
                    async for message in client.messages:
                        if message.topic.matches(echo_topic):
                            end_time = time.time()
                            response_id = message.payload.decode()
                            
                            if response_id == ping_id:
                                return (end_time - start_time) * 1000  # Convert to ms
                            else:
                                return None  # Wrong ping ID
                
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None
    
    def _print_summary(self):
        """Print comprehensive summary of all measurements"""
        print(f"\n📊 COMPREHENSIVE METRICS SUMMARY")
        print("=" * 60)
        print(f"Total measurements: {len(self.results)}")
        print(f"Data saved to: {self.output_file}")
        
        if not self.results:
            print("❌ No data collected")
            return
        
        # Analyze by cube
        for cube_id in self.cube_ids:
            cube_results = [r for r in self.results if r['cube_id'] == cube_id]
            
            if not cube_results:
                continue
                
            print(f"\n📈 Cube {cube_id} Analysis ({len(cube_results)} samples):")
            
            # Extract metrics
            udp_pings = [r['metrics']['udp_ping_ms'] for r in cube_results if r['metrics']['udp_ping_ms'] is not None]
            loop_times = [r['metrics']['loop_time_ms'] for r in cube_results if r['metrics']['loop_time_ms'] is not None]
            mqtt_pings = [r['metrics']['mqtt_ping_ms'] for r in cube_results if r['metrics']['mqtt_ping_ms'] is not None]
            
            # UDP Ping stats
            if udp_pings:
                print(f"   UDP Ping:  avg={sum(udp_pings)/len(udp_pings):.1f}ms, "
                      f"min={min(udp_pings):.1f}ms, max={max(udp_pings):.1f}ms "
                      f"({len(udp_pings)}/{len(cube_results)} success)")
            else:
                print(f"   UDP Ping:  No successful measurements")
            
            # Loop Time stats
            if loop_times:
                print(f"   Loop Time: avg={sum(loop_times)/len(loop_times):.1f}ms, "
                      f"min={min(loop_times)}ms, max={max(loop_times)}ms "
                      f"({len(loop_times)}/{len(cube_results)} success)")
            else:
                print(f"   Loop Time: No successful measurements")
            
            # MQTT Ping stats
            if mqtt_pings:
                print(f"   MQTT Ping: avg={sum(mqtt_pings)/len(mqtt_pings):.1f}ms, "
                      f"min={min(mqtt_pings):.1f}ms, max={max(mqtt_pings):.1f}ms "
                      f"({len(mqtt_pings)}/{len(cube_results)} success)")
            else:
                print(f"   MQTT Ping: No successful measurements")
        
        print(f"\n✅ Comprehensive cube metrics analysis complete!")

def main():
    parser = argparse.ArgumentParser(description="Comprehensive cube metrics monitoring")
    parser.add_argument("--cubes", type=int, nargs="+", default=[1, 6], 
                        help="Cube IDs to monitor (default: 1 6)")
    parser.add_argument("--duration", type=int, default=60, 
                        help="Monitoring duration in seconds (default: 60)")
    parser.add_argument("--interval", type=int, default=3,
                        help="Measurement interval in seconds (default: 3)")
    parser.add_argument("--output", default="cube_metrics.jsonl",
                        help="Output JSONL file (default: cube_metrics.jsonl)")
    parser.add_argument("--mqtt-broker", default="192.168.8.247",
                        help="MQTT broker address (default: 192.168.8.247)")
    
    args = parser.parse_args()
    
    monitor = CubeMetricsMonitor(
        cube_ids=args.cubes,
        output_file=args.output,
        mqtt_broker=args.mqtt_broker
    )
    
    try:
        asyncio.run(monitor.run_monitoring(
            duration_seconds=args.duration,
            interval_seconds=args.interval
        ))
    except KeyboardInterrupt:
        print("\n⏹️  Monitoring interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()