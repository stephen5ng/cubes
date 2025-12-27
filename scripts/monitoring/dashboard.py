#!/usr/bin/env python3

import asyncio
import tkinter as tk
from tkinter import ttk
import aiomqtt
import os
import asyncio.subprocess
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import collections
from datetime import datetime, timedelta

MQTT_SERVER = os.environ.get("MQTT_SERVER", "localhost")
UDP_PORT = 54321

# Read cube IDs from file
with open('cube_ids.txt', 'r') as f:
    CUBE_IDS = [line.strip() for line in f.readlines()]
#CUBE_IDS=CUBE_IDS[:2]
NUM_CUBES = len(CUBE_IDS)

# Map cube IDs to IP addresses: cube 1 -> .21, cube 2 -> .22, etc.
CUBE_IPS = {cube_id: f"192.168.8.{20+int(cube_id)}" for cube_id in CUBE_IDS}

class CubeDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Cube Dashboard")
        
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.closing = False
        
        # Data storage for graphs
        self.graph_data = {}
        for cube_id in CUBE_IDS:
            self.graph_data[cube_id] = {
                'icmp_times': collections.deque(maxlen=1000),
                'udp_times': collections.deque(maxlen=1000),
                'rssi_values': collections.deque(maxlen=1000),
                'timestamps': collections.deque(maxlen=1000)
            }
        
        # Create main frame
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create left panel for cube status
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Create a frame for each cube
        self.cube_frames = {}
        for i, cube_id in enumerate(CUBE_IDS):
            ip = CUBE_IPS[cube_id]
            frame = ttk.LabelFrame(left_panel, text=f"Cube {cube_id} - {ip}")
            frame.pack(fill=tk.X, pady=5)
            
            # Letter display
            letter_label = ttk.Label(frame, text="Letter: ")
            letter_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
            letter_value = ttk.Label(frame, text="-", width=16)
            letter_value.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            
            # NFC display
            nfc_label = ttk.Label(frame, text="NFC: ")
            nfc_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
            nfc_value = ttk.Label(frame, text="-", width=16)
            nfc_value.grid(row=1, column=1, padx=5, pady=5, sticky="w")
            
            # ICMP Ping display
            ping_label = ttk.Label(frame, text="ICMP: ")
            ping_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
            ping_value = ttk.Label(frame, text="-", width=16)
            ping_value.grid(row=2, column=1, padx=5, pady=5, sticky="w")
            
            # UDP Ping display
            udp_label = ttk.Label(frame, text="UDP: ")
            udp_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")
            udp_value = ttk.Label(frame, text="-", width=16)
            udp_value.grid(row=3, column=1, padx=5, pady=5, sticky="w")
            
            # RSSI display
            rssi_label = ttk.Label(frame, text="RSSI: ")
            rssi_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")
            rssi_value = ttk.Label(frame, text="-", width=16)
            rssi_value.grid(row=4, column=1, padx=5, pady=5, sticky="w")
            
            self.cube_frames[cube_id] = {
                "frame": frame,
                "letter": letter_value,
                "nfc": nfc_value,
                "ping": ping_value,
                "udp": udp_value,
                "rssi": rssi_value
            }
        
        # Create right panel for graphs
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(10, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, right_panel)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Create subplots
        self.ax1 = self.fig.add_subplot(311)  # ICMP ping times
        self.ax2 = self.fig.add_subplot(312)  # UDP ping times
        self.ax3 = self.fig.add_subplot(313)  # RSSI values
        
        # Configure plots
        self.ax1.set_title('ICMP Ping Times')
        self.ax1.set_ylabel('Time (ms)')
        self.ax1.grid(True)
        
        self.ax2.set_title('UDP Ping Times')
        self.ax2.set_ylabel('Time (ms)')
        self.ax2.grid(True)
        
        self.ax3.set_title('RSSI Values')
        self.ax3.set_ylabel('RSSI (dBm)')
        self.ax3.set_xlabel('Time')
        self.ax3.grid(True)
        
        # Adjust layout
        self.fig.tight_layout()

    def on_closing(self):
        """Handle window close event"""
        self.closing = True
        self.root.quit()

    def update_graphs(self):
        """Update all graphs with current data"""
        try:
            # Clear previous plots
            self.ax1.clear()
            self.ax2.clear()
            self.ax3.clear()
            
            # Calculate the cutoff time (120 seconds ago)
            cutoff_time = datetime.now() - timedelta(seconds=120)
            
            # Collect all timestamps to determine time range
            all_timestamps = []
            for cube_id in CUBE_IDS:
                # Filter timestamps to only include last 120 seconds
                recent_timestamps = [ts for ts in self.graph_data[cube_id]['timestamps'] if ts >= cutoff_time]
                all_timestamps.extend(recent_timestamps)
            
            if not all_timestamps:
                # No recent data, just set up empty plots
                self.ax1.set_title('ICMP Ping Times (Last 120s)')
                self.ax1.set_ylabel('Time (ms)')
                self.ax1.grid(True)
                
                self.ax2.set_title('UDP Ping Times (Last 120s)')
                self.ax2.set_ylabel('Time (ms)')
                self.ax2.grid(True)
                
                self.ax3.set_title('RSSI Values (Last 120s)')
                self.ax3.set_ylabel('RSSI (dBm)')
                self.ax3.set_xlabel('Time')
                self.ax3.grid(True)
                
                self.canvas.draw()
                return
            
            # Determine time range for recent data
            start_time = min(all_timestamps)
            end_time = max(all_timestamps)
            time_span = (end_time - start_time).total_seconds()
            
            # Plot data for each cube
            colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
            for i, cube_id in enumerate(CUBE_IDS):
                color = colors[i % len(colors)]
                data = self.graph_data[cube_id]
                
                # Filter data to only include last 120 seconds
                recent_indices = [i for i, ts in enumerate(data['timestamps']) if ts >= cutoff_time]
                
                if recent_indices:
                    # Get recent data
                    timestamps = [data['timestamps'][i] for i in recent_indices]
                    icmp_times = [data['icmp_times'][i] for i in recent_indices]
                    udp_times = [data['udp_times'][i] for i in recent_indices]
                    rssi_values = [data['rssi_values'][i] for i in recent_indices]
                    
                    # Convert timestamps to relative time in seconds
                    times = [(ts - start_time).total_seconds() for ts in timestamps]
                    
                    # Plot ICMP times (only if we have valid data)
                    valid_icmp = [(t, v) for t, v in zip(times, icmp_times) if v is not None]
                    if valid_icmp:
                        plot_times, plot_values = zip(*valid_icmp)
                        self.ax1.plot(plot_times, plot_values, color=color, label=f'Cube {cube_id}', marker='o', markersize=3)
                    
                    # Plot UDP times (only if we have valid data)
                    valid_udp = [(t, v) for t, v in zip(times, udp_times) if v is not None]
                    if valid_udp:
                        plot_times, plot_values = zip(*valid_udp)
                        self.ax2.plot(plot_times, plot_values, color=color, label=f'Cube {cube_id}', marker='s', markersize=3)
                    
                    # Plot RSSI values (only if we have valid data)
                    valid_rssi = [(t, v) for t, v in zip(times, rssi_values) if v is not None]
                    if valid_rssi:
                        plot_times, plot_values = zip(*valid_rssi)
                        self.ax3.plot(plot_times, plot_values, color=color, label=f'Cube {cube_id}', marker='^', markersize=3)
            
            # Configure plots with dynamic time axis
            self.ax1.set_title('ICMP Ping Times (Last 120s)')
            self.ax1.set_ylabel('Time (ms)')
            self.ax1.set_xlabel('Time (s)')
            self.ax1.grid(True)
            if self.ax1.get_legend_handles_labels()[0]:  # Only show legend if there are artists
                self.ax1.legend()
            
            # Set time axis limits based on data range (max 120s)
            if time_span > 0:
                max_time = min(time_span, 120)  # Cap at 120 seconds
                self.ax1.set_xlim(0, max_time)
                self.ax2.set_xlim(0, max_time)
                self.ax3.set_xlim(0, max_time)
            
            self.ax2.set_title('UDP Ping Times (Last 120s)')
            self.ax2.set_ylabel('Time (ms)')
            self.ax2.set_xlabel('Time (s)')
            self.ax2.grid(True)
            if self.ax2.get_legend_handles_labels()[0]:  # Only show legend if there are artists
                self.ax2.legend()
            
            self.ax3.set_title('RSSI Values (Last 120s)')
            self.ax3.set_ylabel('RSSI (dBm)')
            self.ax3.set_xlabel('Time (s)')
            self.ax3.grid(True)
            if self.ax3.get_legend_handles_labels()[0]:  # Only show legend if there are artists
                self.ax3.legend()
            
            # Update canvas
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error updating graphs: {e}")

    def update_letter(self, cube_id: str, letter: str):
        if cube_id in self.cube_frames:
            self.cube_frames[cube_id]["letter"].config(text=letter)

    def update_nfc(self, cube_id: str, nfc_data: str):
        if cube_id in self.cube_frames:
            self.cube_frames[cube_id]["nfc"].config(text=nfc_data)
            
    def update_ping(self, cube_id: str, ping_time: str):
        if cube_id in self.cube_frames:
            self.cube_frames[cube_id]["ping"].config(text=ping_time)
            # Add data to graph
            if ping_time != "Timeout":
                try:
                    time_ms = float(ping_time.replace("ms", ""))
                    self.graph_data[cube_id]['icmp_times'].append(time_ms)
                    self.graph_data[cube_id]['timestamps'].append(datetime.now())
                    # Ensure other arrays have the same length
                    while len(self.graph_data[cube_id]['udp_times']) < len(self.graph_data[cube_id]['timestamps']):
                        self.graph_data[cube_id]['udp_times'].append(None)
                    while len(self.graph_data[cube_id]['rssi_values']) < len(self.graph_data[cube_id]['timestamps']):
                        self.graph_data[cube_id]['rssi_values'].append(None)
                except ValueError:
                    pass
            
    def update_udp(self, cube_id: str, udp_time: str):
        if cube_id in self.cube_frames:
            self.cube_frames[cube_id]["udp"].config(text=udp_time)
            # Add data to graph
            if udp_time != "Timeout":
                try:
                    time_ms = float(udp_time.replace("ms", ""))
                    self.graph_data[cube_id]['udp_times'].append(time_ms)
                    self.graph_data[cube_id]['timestamps'].append(datetime.now())
                    # Ensure other arrays have the same length
                    while len(self.graph_data[cube_id]['icmp_times']) < len(self.graph_data[cube_id]['timestamps']):
                        self.graph_data[cube_id]['icmp_times'].append(None)
                    while len(self.graph_data[cube_id]['rssi_values']) < len(self.graph_data[cube_id]['timestamps']):
                        self.graph_data[cube_id]['rssi_values'].append(None)
                except ValueError:
                    pass

    def update_rssi(self, cube_id: str, rssi: str):
        if cube_id in self.cube_frames:
            self.cube_frames[cube_id]["rssi"].config(text=rssi)
            # Add data to graph
            if rssi != "No Response" and rssi != "Error":
                try:
                    rssi_value = float(rssi)
                    self.graph_data[cube_id]['rssi_values'].append(rssi_value)
                    self.graph_data[cube_id]['timestamps'].append(datetime.now())
                    # Ensure other arrays have the same length
                    while len(self.graph_data[cube_id]['icmp_times']) < len(self.graph_data[cube_id]['timestamps']):
                        self.graph_data[cube_id]['icmp_times'].append(None)
                    while len(self.graph_data[cube_id]['udp_times']) < len(self.graph_data[cube_id]['timestamps']):
                        self.graph_data[cube_id]['udp_times'].append(None)
                except ValueError:
                    pass

async def ping_cube(ip: str) -> float:
    try:
        start_time = time.time()
#        print(f"PING_CUBE: {ip}")
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

    def connection_lost(self, exc):
        # Handle connection lost event
        pass

    async def get_response(self, ip: str, timeout: float = 5.0) -> tuple[bytes, tuple]:
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
            await asyncio.sleep(1)
    finally:
        transport.close()

async def mqtt_listener(dashboard):
    async with aiomqtt.Client(MQTT_SERVER) as client:
        await client.subscribe("cube/+/letter")
        await client.subscribe("cube/right/+")
        async for message in client.messages:
            topic_parts = str(message.topic).split('/')
            if len(topic_parts) == 3:
                if topic_parts[1] == "right":
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
    while not dashboard.closing:
        try:
            root.update()
            # Update graphs every 2 seconds
            if int(time.time()) % 2 == 0:
                dashboard.update_graphs()
            await asyncio.sleep(0.1)
        except tk.TclError:
            # Window was closed
            break
    
    # Cancel all tasks
    mqtt_task.cancel()
    icmp_task.cancel()
    udp_task.cancel()
    rssi_task.cancel()
    
    # Wait for tasks to finish
    await asyncio.gather(mqtt_task, icmp_task, udp_task, rssi_task, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main()) 
