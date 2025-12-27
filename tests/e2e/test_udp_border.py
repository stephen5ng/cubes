#!/usr/bin/env python3
"""
Test UDP border message sending
"""

import asyncio
import sys
sys.path.append('.')
from udp_border_sender import udp_border_sender

async def test_udp_border():
    # Initialize UDP sender
    await udp_border_sender.initialize()
    
    print("Testing UDP border messages...")
    print(f"Cube IPs: {udp_border_sender.cube_ips}")
    
    # Test sending a border message to cube 1
    await udp_border_sender.send_border_message("1", "hline_top", "0xFFFF")
    print("Sent: bT0xFFFF to cube 1")
    
    await asyncio.sleep(1)
    
    # Test clearing the border
    await udp_border_sender.send_border_message("1", "hline_top", None)
    print("Sent: bT to cube 1 (clear)")
    
    # Cleanup
    udp_border_sender.close()

if __name__ == "__main__":
    asyncio.run(test_udp_border())