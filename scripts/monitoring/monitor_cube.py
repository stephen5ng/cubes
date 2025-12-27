#!/usr/bin/env python3
"""
Cube monitoring tool - query ESP32 system status via UDP
"""

import socket
import time
import sys

def query_cube(cube_ip, command):
    """Send UDP query to cube and return response"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        
        # Send command
        sock.sendto(command.encode(), (cube_ip, 54321))
        
        # Get response
        response, addr = sock.recvfrom(1024)
        sock.close()
        
        return response.decode().strip()
    except socket.timeout:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"

def monitor_cube(cube_id):
    """Monitor a specific cube"""
    cube_ip = f"192.168.8.{20+int(cube_id)}"
    
    print(f"Monitoring Cube {cube_id} at {cube_ip}")
    print("Commands: ping, rssi, load, mqtt")
    print("Press Ctrl+C to exit\n")
    
    try:
        while True:
            print(f"=== Cube {cube_id} Status ===")
            
            # Test basic connectivity
            ping_result = query_cube(cube_ip, "ping")
            print(f"Ping: {ping_result}")
            
            # Get system load
            load_result = query_cube(cube_ip, "load")
            print(f"Load: {load_result}")
            
            # Get MQTT status  
            mqtt_result = query_cube(cube_ip, "mqtt")
            print(f"MQTT: {mqtt_result}")
            
            # Get WiFi signal
            rssi_result = query_cube(cube_ip, "rssi")
            print(f"RSSI: {rssi_result} dBm")
            
            print()
            time.sleep(5)  # Query every 5 seconds
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 monitor_cube.py <cube_id>")
        print("Example: python3 monitor_cube.py 1")
        sys.exit(1)
    
    cube_id = sys.argv[1]
    monitor_cube(cube_id)