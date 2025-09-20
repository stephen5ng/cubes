#!/usr/bin/env python3
"""
Cube Performance Testing Tool

Usage:
    python3 testperf.py 1 3           # Compare cubes 1 and 3
    python3 testperf.py 1 3 6         # Compare cubes 1, 3, and 6
    python3 testperf.py --all         # Test all available cubes
    python3 testperf.py 1 --samples 5 # Test cube 1 with 5 samples
"""

import socket
import time
import sys
import argparse
from typing import List, Optional, Dict

# Cube IP mapping
CUBE_IPS = {
    1: '192.168.8.21',
    2: '192.168.8.22', 
    3: '192.168.8.23',
    4: '192.168.8.24',
    5: '192.168.8.25',
    6: '192.168.8.26'
}

UDP_PORT = 54321
DEFAULT_SAMPLES = 3
TIMEOUT_SECONDS = 3

class CubePerformanceTester:
    def __init__(self, samples: int = DEFAULT_SAMPLES):
        self.samples = samples
        
    def test_cube_performance(self, ip: str, cube_id: int) -> Dict:
        """Test a single cube's UDP performance"""
        results = {
            'cube_id': cube_id,
            'ip': ip,
            'udp_times': [],
            'timing_times': [],
            'loop_times': [],
            'errors': 0
        }
        
        print(f'Testing Cube {cube_id} ({ip}):')
        
        for i in range(self.samples):
            try:
                udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_sock.settimeout(TIMEOUT_SECONDS)
                
                # UDP ping test
                start = time.time()
                udp_sock.sendto(b'ping', (ip, UDP_PORT))
                response, addr = udp_sock.recvfrom(1024)
                end = time.time()
                udp_ping = (end - start) * 1000
                
                # Timing test
                start = time.time()
                udp_sock.sendto(b'timing', (ip, UDP_PORT))
                response, addr = udp_sock.recvfrom(1024)
                end = time.time()
                timing = (end - start) * 1000
                
                # Extract loop time from response (format: "cube_id:loop_time")
                loop_time = int(response.decode().split(':')[1])
                
                results['udp_times'].append(udp_ping)
                results['timing_times'].append(timing)
                results['loop_times'].append(loop_time)
                
                print(f'  Sample {i+1}: UDP: {udp_ping:.1f}ms, Timing: {timing:.1f}ms, Loop: {loop_time}ms')
                
                udp_sock.close()
                time.sleep(0.5)  # Brief pause between samples
                
            except Exception as e:
                print(f'  Sample {i+1}: ERROR: {e}')
                results['errors'] += 1
                if 'udp_sock' in locals():
                    udp_sock.close()
        
        return results
    
    def calculate_stats(self, times: List[float]) -> Dict:
        """Calculate statistics for a list of timing measurements"""
        if not times:
            return {'avg': 0, 'min': 0, 'max': 0, 'count': 0}
            
        return {
            'avg': sum(times) / len(times),
            'min': min(times),
            'max': max(times),
            'count': len(times)
        }
    
    def test_cubes(self, cube_ids: List[int]) -> Dict:
        """Test multiple cubes and return results"""
        results = {}
        
        print(f'Cube Performance Test - {self.samples} samples per cube')
        print('=' * 60)
        
        for cube_id in cube_ids:
            if cube_id not in CUBE_IPS:
                print(f'Warning: Cube {cube_id} not in IP mapping, skipping')
                continue
                
            ip = CUBE_IPS[cube_id]
            cube_results = self.test_cube_performance(ip, cube_id)
            results[cube_id] = cube_results
            print()  # Blank line between cubes
        
        return results
    
    def print_summary(self, results: Dict):
        """Print summary statistics"""
        print('PERFORMANCE SUMMARY')
        print('=' * 60)
        print(f'{"Cube":<6} {"UDP Avg":<10} {"UDP Range":<15} {"Timing Avg":<12} {"Loop Avg":<8} {"Errors":<6}')
        print('-' * 60)
        
        cube_stats = []
        
        for cube_id, data in results.items():
            if data['errors'] == self.samples:
                print(f'{cube_id:<6} {"NO RESPONSE":<10}')
                continue
                
            udp_stats = self.calculate_stats(data['udp_times'])
            timing_stats = self.calculate_stats(data['timing_times'])
            loop_stats = self.calculate_stats(data['loop_times'])
            
            cube_stats.append({
                'cube_id': cube_id,
                'udp_avg': udp_stats['avg'],
                'timing_avg': timing_stats['avg'],
                'loop_avg': loop_stats['avg']
            })
            
            udp_range = f"{udp_stats['min']:.1f}-{udp_stats['max']:.1f}ms" if udp_stats['count'] > 1 else f"{udp_stats['avg']:.1f}ms"
            
            print(f'{cube_id:<6} {udp_stats["avg"]:<10.1f} {udp_range:<15} {timing_stats["avg"]:<12.1f} {loop_stats["avg"]:<8.1f} {data["errors"]:<6}')
        
        # Print comparative analysis if multiple cubes
        if len(cube_stats) > 1:
            print()
            print('COMPARATIVE ANALYSIS')
            print('-' * 40)
            
            # Find best and worst performers
            best_udp = min(cube_stats, key=lambda x: x['udp_avg'])
            worst_udp = max(cube_stats, key=lambda x: x['udp_avg'])
            
            print(f'Fastest UDP: Cube {best_udp["cube_id"]} ({best_udp["udp_avg"]:.1f}ms)')
            print(f'Slowest UDP: Cube {worst_udp["cube_id"]} ({worst_udp["udp_avg"]:.1f}ms)')
            
            if best_udp['cube_id'] != worst_udp['cube_id']:
                ratio = worst_udp['udp_avg'] / best_udp['udp_avg']
                print(f'Performance ratio: {ratio:.1f}x difference')


def get_all_responsive_cubes() -> List[int]:
    """Quick check to find all responsive cubes"""
    responsive = []
    print('Scanning for responsive cubes...')
    
    for cube_id, ip in CUBE_IPS.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1)
            sock.sendto(b'ping', (ip, UDP_PORT))
            response, addr = sock.recvfrom(1024)
            responsive.append(cube_id)
            print(f'  Cube {cube_id}: ✓')
            sock.close()
        except:
            print(f'  Cube {cube_id}: ✗')
    
    print()
    return responsive


def main():
    parser = argparse.ArgumentParser(description='Test ESP32 cube UDP performance')
    parser.add_argument('cubes', nargs='*', type=int, help='Cube numbers to test (1-6)')
    parser.add_argument('--all', action='store_true', help='Test all responsive cubes')
    parser.add_argument('--samples', type=int, default=DEFAULT_SAMPLES, 
                       help=f'Number of samples per cube (default: {DEFAULT_SAMPLES})')
    
    args = parser.parse_args()
    
    if args.all:
        cube_ids = get_all_responsive_cubes()
        if not cube_ids:
            print('No responsive cubes found!')
            return 1
    elif args.cubes:
        cube_ids = args.cubes
    else:
        print('Please specify cube numbers or use --all')
        print('Example: python3 testperf.py 1 3')
        return 1
    
    # Validate cube IDs
    invalid_cubes = [c for c in cube_ids if c not in CUBE_IPS]
    if invalid_cubes:
        print(f'Invalid cube numbers: {invalid_cubes}')
        print(f'Valid cubes: {list(CUBE_IPS.keys())}')
        return 1
    
    tester = CubePerformanceTester(args.samples)
    results = tester.test_cubes(cube_ids)
    tester.print_summary(results)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())