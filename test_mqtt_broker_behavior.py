#!/usr/bin/env python3
"""
Test MQTT broker behavior to see if it's causing message batching/delays.
"""

import asyncio
import time
import paho.mqtt.client as mqtt
import statistics
import threading
from collections import defaultdict

class MQTTBrokerTest:
    def __init__(self, mqtt_host="192.168.8.247"):
        self.mqtt_host = mqtt_host
        self.running = True
        self.test_results = {}
        
    async def test_single_vs_burst_messages(self):
        """Test if broker handles single messages vs burst differently"""
        print("Testing MQTT broker message handling patterns...")
        
        # Test 1: Single messages with delays
        print("\n1. Testing single messages (one every 250ms)")
        single_latencies = await self.test_message_pattern("single", single_message=True)
        
        # Test 2: Burst of 6 messages (like random_letters.sh)
        print("\n2. Testing burst messages (6 at once, then 250ms delay)")
        burst_latencies = await self.test_message_pattern("burst", single_message=False)
        
        # Test 3: Different QoS levels
        print("\n3. Testing different QoS levels")
        qos0_latencies = await self.test_qos_impact(0)
        qos1_latencies = await self.test_qos_impact(1)
        
        self.analyze_mqtt_results(single_latencies, burst_latencies, qos0_latencies, qos1_latencies)
        
    async def test_message_pattern(self, test_name, single_message=True, iterations=20):
        """Test specific message sending pattern"""
        received_messages = []
        send_times = {}
        
        # Set up subscriber
        sub_client = mqtt.Client(client_id=f"test_sub_{test_name}")
        
        def on_message(client, userdata, msg):
            receive_time = time.time()
            message_id = msg.payload.decode()
            received_messages.append((receive_time, message_id))
            
        def on_connect_sub(client, userdata, flags, rc):
            client.subscribe("test/latency")
            
        sub_client.on_connect = on_connect_sub
        sub_client.on_message = on_message
        
        # Set up publisher
        pub_client = mqtt.Client(client_id=f"test_pub_{test_name}")
        
        try:
            sub_client.connect(self.mqtt_host, 1883, 60)
            pub_client.connect(self.mqtt_host, 1883, 60)
            sub_client.loop_start()
        except Exception as e:
            print(f"Connection failed: {e}")
            return []
            
        await asyncio.sleep(1)  # Let connections establish
        
        print(f"  Sending {iterations} message sets...")
        
        for i in range(iterations):
            if single_message:
                # Send one message
                message_id = f"{test_name}_{i}"
                send_time = time.time()
                send_times[message_id] = send_time
                pub_client.publish("test/latency", message_id)
                print(f"    Sent {message_id}")
                
                await asyncio.sleep(0.25)
            else:
                # Send burst of 6 messages (like random_letters.sh)
                for j in range(6):
                    message_id = f"{test_name}_{i}_{j}"
                    send_time = time.time()
                    send_times[message_id] = send_time
                    pub_client.publish("test/latency", message_id)
                    
                print(f"    Sent burst {i} (6 messages)")
                await asyncio.sleep(0.25)
                
        await asyncio.sleep(2)  # Wait for final messages
        
        sub_client.loop_stop()
        sub_client.disconnect()
        pub_client.disconnect()
        
        # Calculate latencies
        latencies = []
        for receive_time, message_id in received_messages:
            if message_id in send_times:
                latency = (receive_time - send_times[message_id]) * 1000
                latencies.append(latency)
                
        print(f"  Received {len(received_messages)}/{len(send_times)} messages")
        return latencies
        
    async def test_qos_impact(self, qos_level):
        """Test impact of QoS level on latency"""
        print(f"  Testing QoS {qos_level}...")
        
        received_messages = []
        send_times = {}
        
        sub_client = mqtt.Client(client_id=f"test_qos_sub_{qos_level}")
        pub_client = mqtt.Client(client_id=f"test_qos_pub_{qos_level}")
        
        def on_message(client, userdata, msg):
            receive_time = time.time()
            message_id = msg.payload.decode()
            received_messages.append((receive_time, message_id))
            
        def on_connect_sub(client, userdata, flags, rc):
            client.subscribe("test/qos", qos_level)
            
        sub_client.on_connect = on_connect_sub
        sub_client.on_message = on_message
        
        try:
            sub_client.connect(self.mqtt_host, 1883, 60)
            pub_client.connect(self.mqtt_host, 1883, 60)
            sub_client.loop_start()
        except Exception as e:
            print(f"    QoS {qos_level} connection failed: {e}")
            return []
            
        await asyncio.sleep(1)
        
        # Send 10 test messages
        for i in range(10):
            message_id = f"qos{qos_level}_{i}"
            send_time = time.time()
            send_times[message_id] = send_time
            pub_client.publish("test/qos", message_id, qos=qos_level)
            await asyncio.sleep(0.1)
            
        await asyncio.sleep(2)
        
        sub_client.loop_stop()
        sub_client.disconnect()
        pub_client.disconnect()
        
        # Calculate latencies
        latencies = []
        for receive_time, message_id in received_messages:
            if message_id in send_times:
                latency = (receive_time - send_times[message_id]) * 1000
                latencies.append(latency)
                
        return latencies
        
    def analyze_mqtt_results(self, single_latencies, burst_latencies, qos0_latencies, qos1_latencies):
        """Analyze MQTT test results"""
        print("\n" + "="*60)
        print("MQTT BROKER ANALYSIS")
        print("="*60)
        
        def print_latency_stats(latencies, name):
            if not latencies:
                print(f"\n{name}: No data")
                return
                
            print(f"\n{name}:")
            print(f"  Count: {len(latencies)}")
            print(f"  Mean: {statistics.mean(latencies):.2f}ms")
            print(f"  Median: {statistics.median(latencies):.2f}ms")
            print(f"  Min: {min(latencies):.2f}ms")
            print(f"  Max: {max(latencies):.2f}ms")
            print(f"  Std Dev: {statistics.stdev(latencies):.2f}ms" if len(latencies) > 1 else "  Std Dev: N/A")
            
            # Count high latency messages
            high_latency = [l for l in latencies if l > 10]  # >10ms
            very_high = [l for l in latencies if l > 50]  # >50ms
            
            if high_latency:
                print(f"  High latency (>10ms): {len(high_latency)} ({len(high_latency)/len(latencies)*100:.1f}%)")
            if very_high:
                print(f"  Very high latency (>50ms): {len(very_high)}")
                
        print_latency_stats(single_latencies, "Single Message Pattern")
        print_latency_stats(burst_latencies, "Burst Message Pattern")
        print_latency_stats(qos0_latencies, "QoS 0 (Fire and Forget)")
        print_latency_stats(qos1_latencies, "QoS 1 (At Least Once)")
        
        # Compare patterns
        if single_latencies and burst_latencies:
            single_mean = statistics.mean(single_latencies)
            burst_mean = statistics.mean(burst_latencies)
            
            print(f"\nPattern Comparison:")
            print(f"  Single message mean: {single_mean:.2f}ms")
            print(f"  Burst message mean: {burst_mean:.2f}ms")
            
            if burst_mean > single_mean * 1.5:
                print("  ❌ ISSUE: Burst messages have significantly higher latency")
                print("     This suggests the broker or network is struggling with bursts")
            else:
                print("  ✅ Burst and single message latencies are similar")
                
        # QoS comparison
        if qos0_latencies and qos1_latencies:
            qos0_mean = statistics.mean(qos0_latencies)
            qos1_mean = statistics.mean(qos1_latencies)
            
            print(f"\nQoS Comparison:")
            print(f"  QoS 0 mean: {qos0_mean:.2f}ms")
            print(f"  QoS 1 mean: {qos1_mean:.2f}ms")
            print(f"  QoS 1 overhead: {qos1_mean - qos0_mean:.2f}ms")

async def main():
    test = MQTTBrokerTest()
    
    import signal
    def signal_handler(sig, frame):
        test.running = False
        
    signal.signal(signal.SIGINT, signal_handler)
    
    await test.test_single_vs_burst_messages()

if __name__ == "__main__":
    asyncio.run(main())