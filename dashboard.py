#!/usr/bin/env python3

import asyncio
import tkinter as tk
from tkinter import ttk
import aiomqtt
import os
import asyncio.subprocess
import time

MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")
UDP_PORT = 54321

# Read cube IDs from file
with open('cube_ids.txt', 'r') as f:
    CUBE_IDS = [line.strip() for line in f.readlines()]
NUM_CUBES = len(CUBE_IDS)

# Map cube IDs to IP addresses (even numbers from 192.168.8.0 to 192.168.8.30)
CUBE_IPS = {cube_id: f"192.168.8.{20+i*2}" for i, cube_id in enumerate(CUBE_IDS)}

class CubeDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Cube Dashboard")
        
        # Create a frame for each cube
        self.cube_frames = {}
        for i, cube_id in enumerate(CUBE_IDS):
            ip = CUBE_IPS[cube_id]
            frame = ttk.LabelFrame(root, text=f"Cube {cube_id} - {ip}")
            frame.grid(row=i//3, column=i%3, padx=10, pady=5, sticky="nsew")
            
            # Letter display
            letter_label = ttk.Label(frame, text="Letter: ")
            letter_label.grid(row=0, column=0, padx=5, pady=5)
            letter_value = ttk.Label(frame, text="-", width=16)
            letter_value.grid(row=0, column=1, padx=5, pady=5)
            
            # NFC display
            nfc_label = ttk.Label(frame, text="NFC: ")
            nfc_label.grid(row=1, column=0, padx=5, pady=5)
            nfc_value = ttk.Label(frame, text="-", width=16)
            nfc_value.grid(row=1, column=1, padx=5, pady=5)
            
            # ICMP Ping display
            ping_label = ttk.Label(frame, text="ICMP: ")
            ping_label.grid(row=2, column=0, padx=5, pady=5)
            ping_value = ttk.Label(frame, text="-", width=16)
            ping_value.grid(row=2, column=1, padx=5, pady=5)
            
            # UDP Ping display
            udp_label = ttk.Label(frame, text="UDP: ")
            udp_label.grid(row=3, column=0, padx=5, pady=5)
            udp_value = ttk.Label(frame, text="-", width=16)
            udp_value.grid(row=3, column=1, padx=5, pady=5)
            
            # RSSI display
            rssi_label = ttk.Label(frame, text="RSSI: ")
            rssi_label.grid(row=4, column=0, padx=5, pady=5)
            rssi_value = ttk.Label(frame, text="-", width=16)
            rssi_value.grid(row=4, column=1, padx=5, pady=5)
            
            self.cube_frames[cube_id] = {
                "frame": frame,
                "letter": letter_value,
                "nfc": nfc_value,
                "ping": ping_value,
                "udp": udp_value,
                "rssi": rssi_value
            }
        
        # Configure grid weights
        for i in range(2):  # 2 rows
            root.grid_rowconfigure(i, weight=1)
        for i in range(3):  # 3 columns
            root.grid_columnconfigure(i, weight=1)

    def update_letter(self, cube_id: str, letter: str):
        if cube_id in self.cube_frames:
            self.cube_frames[cube_id]["letter"].config(text=letter)

    def update_nfc(self, cube_id: str, nfc_data: str):
        if cube_id in self.cube_frames:
            self.cube_frames[cube_id]["nfc"].config(text=nfc_data)
            
    def update_ping(self, cube_id: str, ping_time: str):
        if cube_id in self.cube_frames:
            self.cube_frames[cube_id]["ping"].config(text=ping_time)
            
    def update_udp(self, cube_id: str, udp_time: str):
        if cube_id in self.cube_frames:
            self.cube_frames[cube_id]["udp"].config(text=udp_time)

    def update_rssi(self, cube_id: str, rssi: str):
        if cube_id in self.cube_frames:
            self.cube_frames[cube_id]["rssi"].config(text=rssi)

async def ping_cube(ip: str) -> float:
    try:
        start_time = time.time()
        print(f"PING_CUBE: {ip}")
        proc = await asyncio.create_subprocess_exec(
            'ping', '-c', '1', '-W', '1', ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        
        await proc.communicate()
        
        if proc.returncode == 0:
            return round((time.time() - start_time) * 1000, 1)  # Convert to ms
        return -1
    except Exception:
        return -1

class UDPClientProtocol:
    def __init__(self):
        self.transport = None
        self.responses = {}  # Track responses by IP

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        # Store response for the IP it came from
        self.responses[addr[0]] = (data, addr)

    def error_received(self, exc):
        print(f'UDP Protocol Error: {exc}')

    async def get_response(self, ip: str, timeout: float = 1.0) -> tuple[bytes, tuple]:
        try:
            # Wait for response from specific IP
            start_time = time.time()
            while time.time() - start_time < timeout:
                if ip in self.responses:
                    response = self.responses.pop(ip)
                    return response
                await asyncio.sleep(0.01)  # Small delay to prevent busy loop
            raise asyncio.TimeoutError()
        except Exception as e:
            print(f"Error getting response from {ip}: {e}")
            raise

async def udp_ping_cube(transport, protocol, ip: str) -> float:
    try:
        start_time = time.time()
        transport.sendto("ping".encode(), (ip, UDP_PORT))
        
        try:
            data, addr = await protocol.get_response(ip)
            if data.decode() == "pong":
                return round((time.time() - start_time) * 1000, 1)  # Convert to ms
        except asyncio.TimeoutError:
            pass
        return -1
    except Exception as e:
        print(f"UDP ping error: {e}")
        return -1

async def icmp_monitor(dashboard):
    while True:
        for cube_id, ip in CUBE_IPS.items():
            ping_time = await ping_cube(ip)
            if ping_time >= 0:
                dashboard.root.after(0, dashboard.update_ping, cube_id, f"{ping_time}ms")
            else:
                dashboard.root.after(0, dashboard.update_ping, cube_id, "Timeout")

async def udp_monitor(dashboard):
    # Create UDP socket for ping-pong
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UDPClientProtocol(),
        local_addr=('0.0.0.0', 0))  # Use random source port
    
    try:
        while True:
            # Create tasks for all cubes
            tasks = [
                udp_ping_cube(transport, protocol, ip) 
                for ip in CUBE_IPS.values()
            ]
            # Run all pings in parallel
            results = await asyncio.gather(*tasks)
            
            # Update dashboard with results
            for cube_id, ping_time in zip(CUBE_IPS.keys(), results):
                if ping_time >= 0:
                    dashboard.root.after(0, dashboard.update_udp, cube_id, f"{ping_time}ms")
                else:
                    dashboard.root.after(0, dashboard.update_udp, cube_id, "Timeout")
    finally:
        transport.close()

async def mqtt_listener(dashboard):
    async with aiomqtt.Client(MQTT_SERVER) as client:
        await client.subscribe("cube/+/letter")
        await client.subscribe("cube/nfc/+")
        async for message in client.messages:
            topic_parts = str(message.topic).split('/')
            if len(topic_parts) == 3:
                if topic_parts[1] == "nfc":
                    cube_id = topic_parts[2]
                    nfc_data = message.payload.decode()
                    dashboard.root.after(0, dashboard.update_nfc, cube_id, nfc_data)
                else:
                    cube_id = topic_parts[1]
                    letter = message.payload.decode()
                    dashboard.root.after(0, dashboard.update_letter, cube_id, letter)

async def get_rssi(transport, protocol, ip: str) -> str:
    try:
        transport.sendto("rssi".encode(), (ip, UDP_PORT))
        
        try:
            data, addr = await protocol.get_response(ip)
            return data.decode()
        except asyncio.TimeoutError:
            pass
        return "No Response"
    except Exception as e:
        print(f"RSSI error: {e}")
        return "Error"

async def rssi_monitor(dashboard):
    # Create UDP socket for RSSI monitoring
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UDPClientProtocol(),
        local_addr=('0.0.0.0', 0))
    
    try:
        while True:
            # Create tasks for all cubes
            tasks = [
                get_rssi(transport, protocol, ip)
                for ip in CUBE_IPS.values()
            ]
            # Get all RSSI values in parallel
            results = await asyncio.gather(*tasks)
            
            # Update dashboard with results
            for cube_id, rssi in zip(CUBE_IPS.keys(), results):
                dashboard.root.after(0, dashboard.update_rssi, cube_id, rssi)
    finally:
        transport.close()

async def main():
    root = tk.Tk()
    dashboard = CubeDashboard(root)
    
    # Create tasks for MQTT listener and monitors
    mqtt_task = asyncio.create_task(mqtt_listener(dashboard))
    icmp_task = asyncio.create_task(icmp_monitor(dashboard))
    udp_task = asyncio.create_task(udp_monitor(dashboard))
    rssi_task = asyncio.create_task(rssi_monitor(dashboard))
    
    # Update the Tkinter window
    while True:
        root.update()
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main()) 