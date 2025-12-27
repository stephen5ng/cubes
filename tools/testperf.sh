#!/bin/bash

python3 -c "
import socket
import time

def test_cube_performance(ip, cube_id, firmware_type):
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.settimeout(3)

    try:
        # UDP ping test
        start = time.time()
        udp_sock.sendto(b'ping', (ip, 54321))
        response, addr = udp_sock.recvfrom(1024)
        end = time.time()
        udp_ping = (end-start)*1000

        # Timing test
        start = time.time()
        udp_sock.sendto(b'timing', (ip, 54321))
        response, addr = udp_sock.recvfrom(1024)
        end = time.time()
        timing = (end-start)*1000
        loop_time = response.decode().split(':')[1]

        print(f'Cube {cube_id} ({firmware_type}) - UDP: {udp_ping:.1f}ms, Timing: {timing:.1f}ms, Loop: {loop_time}ms')
        return udp_ping
    except Exception as e:
        print(f'Cube {cube_id} ({firmware_type}) - ERROR: {e}')
        return None

print('Performance Test After Code Change:')
print('=' * 50)

# Test Cube 1 (reference)
print('Testing Cube 1:')
cube1_times = []
for i in range(10):
    udp_time = test_cube_performance('192.168.8.21', 1, 'original')
    if udp_time:
        cube1_times.append(udp_time)
    time.sleep(1)

print()

print('Testing Cube 6 (with code change):')
cube5_times = []
for i in range(10):
    udp_time = test_cube_performance('192.168.8.26', 6, 'modified')
    if udp_time:
        cube5_times.append(udp_time)
    time.sleep(1)

print()
print('Results After Code Change:')
print('=' * 50)
if cube1_times:
    cube1_avg = sum(cube1_times) / len(cube1_times)
    print(f'Cube 1: {cube1_avg:.1f}ms average')

if cube5_times:
    cube5_avg = sum(cube5_times) / len(cube5_times)
    print(f'Cube 5: {cube5_avg:.1f}ms average')

    if cube1_times:
        improvement = ((818.1 - cube5_avg) / 818.1) * 100 if cube5_avg < 818.1 else ((cube5_avg - 818.1) / 818.1) * 100
        print(f'Change from baseline (818.1ms): {improvement:.1f}% {"improvement" if cube5_avg < 818.1 else \"worse\"}')

        diff = abs(cube5_avg - cube1_avg)
        print(f'Difference from Cube 1: {diff:.1f}ms')
else:
    print('Cube 5: No response')
"