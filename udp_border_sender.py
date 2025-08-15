#!/usr/bin/env python3
"""
UDP Border Message Sender

Handles border messages via UDP instead of MQTT for improved performance.
Border messages are fire-and-forget visual feedback that can tolerate packet loss.
"""

import asyncio
import logging
import json
from typing import Optional, Dict

UDP_PORT = 54321

class UDPBorderSender:
    def __init__(self):
        self.cube_ips: Dict[str, str] = {}
        self.transport = None
        self.protocol = None
        
    async def initialize(self):
        """Initialize UDP transport"""
        loop = asyncio.get_event_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: UDPBorderProtocol(),
            local_addr=('0.0.0.0', 0)  # Use random source port
        )
        
        # Load cube IP mappings
        try:
            with open('cube_ids.txt', 'r') as f:
                cube_ids = [line.strip() for line in f.readlines()]
            # Map cube IDs to IP addresses: cube 1 -> .21, cube 2 -> .22, etc.
            self.cube_ips = {cube_id: f"192.168.8.{20+int(cube_id)}" for cube_id in cube_ids}
            logging.info(f"Loaded {len(self.cube_ips)} cube IP mappings")
        except FileNotFoundError:
            logging.warning("cube_ids.txt not found, UDP border sending disabled")
            
    async def send_border_message(self, cube_id: str, border_type: str, color: Optional[str]):
        """Send border message via UDP using simple protocol"""
        if not self.transport or cube_id not in self.cube_ips:
            return
            
        ip = self.cube_ips[cube_id]
        
        # Map border types to single letters
        border_codes = {
            "hline_top": "T",
            "hline_bottom": "B", 
            "vline_left": "L",
            "vline_right": "R"
        }
        
        if border_type not in border_codes:
            logging.warning(f"Unknown border type: {border_type}")
            return
            
        # Format: "b" + code + color (e.g., "bT0xFFFF" or "bT" for clear)
        code = border_codes[border_type]
        message = f"b{code}{color or ''}"
        
        try:
            data = message.encode('utf-8')
            self.transport.sendto(data, (ip, UDP_PORT))
            print(f"UDP BORDER: Sent {message} to cube {cube_id} ({ip})")
            logging.debug(f"Sent UDP border to {cube_id} ({ip}): {message}")
        except Exception as e:
            print(f"UDP BORDER ERROR: Failed to send to cube {cube_id}: {e}")
            logging.error(f"Failed to send UDP border to {cube_id}: {e}")
            
    def close(self):
        """Close UDP transport"""
        if self.transport:
            self.transport.close()

class UDPBorderProtocol:
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        # We don't expect responses for border messages
        pass

    def error_received(self, exc):
        logging.error(f'UDP Border Protocol Error: {exc}')

    def connection_lost(self, exc):
        pass

# Global instance for main.py to use
udp_border_sender = UDPBorderSender()