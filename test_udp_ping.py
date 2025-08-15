#!/usr/bin/env python3
"""
Test UDP ping to verify ESP32 is receiving UDP messages
"""

import asyncio
import socket

async def test_udp_ping():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    
    # Test basic ping first
    print("Testing UDP ping to cube 1...")
    sock.sendto(b"ping", ("192.168.8.21", 54321))
    
    try:
        response, addr = sock.recvfrom(1024)
        print(f"Ping response: {response.decode()} from {addr}")
    except socket.timeout:
        print("No ping response (timeout)")
    
    # Test border message
    print("Testing UDP border message...")
    sock.sendto(b"bT0xFFFF", ("192.168.8.21", 54321))
    print("Sent border message: bT0xFFFF")
    
    sock.close()

if __name__ == "__main__":
    asyncio.run(test_udp_ping())