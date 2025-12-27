#!/usr/bin/env python3
"""
Network diagnostics for MQTT latency issues.
"""

import subprocess
import time
import statistics
import asyncio
import threading

def ping_test(host="192.168.8.247", count=20):
    """Test network latency to MQTT broker"""
    print(f"Pinging {host}...")
    
    try:
        result = subprocess.run([
            "ping", "-c", str(count), host
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"Ping failed: {result.stderr}")
            return None
            
        # Parse ping results
        lines = result.stdout.split('\n')
        times = []
        
        for line in lines:
            if "time=" in line:
                # Extract time value
                time_part = line.split("time=")[1].split()[0]
                times.append(float(time_part))
                
        if times:
            print(f"Ping results (ms):")
            print(f"  Mean: {statistics.mean(times):.2f}")
            print(f"  Min: {min(times):.2f}")
            print(f"  Max: {max(times):.2f}")
            print(f"  Std Dev: {statistics.stdev(times):.2f}")
            
            # Check for packet loss
            if "packet loss" in result.stdout:
                loss_line = [l for l in lines if "packet loss" in l][0]
                print(f"  {loss_line.split(',')[-2].strip()}")
                
        return times
        
    except subprocess.TimeoutExpired:
        print("Ping test timed out")
        return None
    except Exception as e:
        print(f"Ping test failed: {e}")
        return None

def check_wifi_signal():
    """Check WiFi signal strength on macOS"""
    try:
        # Get WiFi info using airport utility
        result = subprocess.run([
            "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
            "-I"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("WiFi Signal Info:")
            lines = result.stdout.split('\n')
            for line in lines:
                if any(key in line.strip() for key in ['SSID', 'RSSI', 'noise', 'channel']):
                    print(f"  {line.strip()}")
        else:
            print("Could not get WiFi info")
            
    except Exception as e:
        print(f"WiFi check failed: {e}")

def check_system_load():
    """Check system CPU and memory load"""
    try:
        # Get load average
        result = subprocess.run(["uptime"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"System load: {result.stdout.strip()}")
            
        # Get memory usage
        result = subprocess.run(["vm_stat"], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines[:5]:  # First few lines have key info
                if line.strip():
                    print(f"Memory: {line.strip()}")
                    
    except Exception as e:
        print(f"System load check failed: {e}")

def check_mqtt_broker_load(host="192.168.8.247"):
    """Check if MQTT broker is responsive"""
    import paho.mqtt.client as mqtt
    
    connection_times = []
    
    def on_connect(client, userdata, flags, rc):
        connect_time = time.time() - userdata['start_time']
        connection_times.append(connect_time * 1000)  # Convert to ms
        client.disconnect()
        
    print(f"Testing MQTT broker responsiveness...")
    
    for i in range(5):
        try:
            client = mqtt.Client(client_id=f"diagnostic_{i}")
            client.on_connect = on_connect
            client.user_data_set({'start_time': time.time()})
            
            start_time = time.time()
            client.connect(host, 1883, 60)
            client.loop_forever()  # Will exit when disconnected in on_connect
            
        except Exception as e:
            print(f"MQTT connection {i} failed: {e}")
            
        time.sleep(0.5)
        
    if connection_times:
        print(f"MQTT Connection Times (ms):")
        print(f"  Mean: {statistics.mean(connection_times):.2f}")
        print(f"  Min: {min(connection_times):.2f}")
        print(f"  Max: {max(connection_times):.2f}")
        
        if max(connection_times) > 100:  # >100ms is concerning
            print(f"  WARNING: Slow MQTT connections detected!")

async def main():
    print("Network Diagnostics for MQTT Latency Issues")
    print("=" * 50)
    
    # Test 1: Basic network connectivity
    print("\n1. Network Connectivity Test")
    ping_test()
    
    # Test 2: WiFi signal strength
    print("\n2. WiFi Signal Check")
    check_wifi_signal()
    
    # Test 3: System load
    print("\n3. System Load Check")
    check_system_load()
    
    # Test 4: MQTT broker responsiveness
    print("\n4. MQTT Broker Responsiveness")
    check_mqtt_broker_load()
    
    print("\n" + "=" * 50)
    print("Diagnostics complete")

if __name__ == "__main__":
    asyncio.run(main())