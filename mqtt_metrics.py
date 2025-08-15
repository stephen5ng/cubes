#!/usr/bin/env python3
"""
MQTT Performance Metrics Collection

Collects metrics to diagnose MQTT latency issues and measure impact
of retained vs non-retained message architectures.
"""

import time
import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json

@dataclass
class MqttMetrics:
    """Tracks MQTT broker and client performance metrics"""
    
    # Message volume metrics
    messages_published_total: int = 0
    messages_published_retained: int = 0
    messages_received_total: int = 0
    
    # Timing metrics (in milliseconds)
    publish_latencies: deque = field(default_factory=lambda: deque(maxlen=1000))
    roundtrip_latencies: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    # Queue metrics
    publish_queue_sizes: deque = field(default_factory=lambda: deque(maxlen=1000))
    max_queue_size_seen: int = 0
    
    # Topic-specific metrics
    topic_message_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    topic_retained_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Broker connection metrics  
    connection_failures: int = 0
    reconnection_count: int = 0
    last_connection_time: Optional[float] = None
    
    # Latency tracking for end-to-end measurement
    pending_roundtrips: Dict[str, float] = field(default_factory=dict)
    
    def record_publish(self, topic: str, retained: bool, queue_size: int, timestamp_ms: Optional[float] = None):
        """Record a message publish event"""
        now = timestamp_ms or time.time() * 1000
        
        self.messages_published_total += 1
        if retained:
            self.messages_published_retained += 1
            self.topic_retained_counts[topic] += 1
            
        self.topic_message_counts[topic] += 1
        self.publish_queue_sizes.append(queue_size)
        self.max_queue_size_seen = max(self.max_queue_size_seen, queue_size)
        
        # Track roundtrip latency for special echo topics
        if topic.startswith("test/echo/"):
            echo_id = topic.split("/")[-1]
            self.pending_roundtrips[echo_id] = now
    
    def record_receive(self, topic: str, timestamp_ms: Optional[float] = None):
        """Record a message receive event"""
        now = timestamp_ms or time.time() * 1000
        
        self.messages_received_total += 1
        
        # Complete roundtrip measurement for echo topics
        if topic.startswith("test/echo/response/"):
            echo_id = topic.split("/")[-1]
            if echo_id in self.pending_roundtrips:
                latency = now - self.pending_roundtrips[echo_id]
                self.roundtrip_latencies.append(latency)
                del self.pending_roundtrips[echo_id]
    
    def record_connection_event(self, event_type: str):
        """Record connection events (connect, disconnect, reconnect)"""
        now = time.time()
        if event_type == "connect":
            self.last_connection_time = now
        elif event_type == "disconnect":
            self.connection_failures += 1
        elif event_type == "reconnect":
            self.reconnection_count += 1
    
    def get_stats(self) -> Dict:
        """Get current statistics summary"""
        now = time.time() * 1000
        
        # Calculate percentiles for latencies
        publish_latencies = list(self.publish_latencies)
        roundtrip_latencies = list(self.roundtrip_latencies)
        queue_sizes = list(self.publish_queue_sizes)
        
        def percentile(data: List[float], p: int) -> float:
            if not data:
                return 0.0
            sorted_data = sorted(data)
            k = (len(sorted_data) - 1) * p / 100
            f = int(k)
            c = k - f
            if f == len(sorted_data) - 1:
                return sorted_data[f]
            return sorted_data[f] * (1 - c) + sorted_data[f + 1] * c
        
        # Categorize topics by type
        letter_topics = {k: v for k, v in self.topic_message_counts.items() if "/letter" in k}
        border_topics = {k: v for k, v in self.topic_message_counts.items() if "/border_" in k}
        nfc_topics = {k: v for k, v in self.topic_message_counts.items() if "/nfc/" in k}
        
        return {
            "timestamp_ms": now,
            "messages": {
                "published_total": self.messages_published_total,
                "published_retained": self.messages_published_retained,
                "published_non_retained": self.messages_published_total - self.messages_published_retained,
                "received_total": self.messages_received_total,
                "retention_rate": self.messages_published_retained / max(1, self.messages_published_total)
            },
            "latency_ms": {
                "roundtrip_p50": percentile(roundtrip_latencies, 50),
                "roundtrip_p95": percentile(roundtrip_latencies, 95),
                "roundtrip_p99": percentile(roundtrip_latencies, 99),
                "roundtrip_max": max(roundtrip_latencies) if roundtrip_latencies else 0,
                "samples": len(roundtrip_latencies)
            },
            "queue": {
                "current_size": queue_sizes[-1] if queue_sizes else 0,
                "max_size": self.max_queue_size_seen,
                "avg_size": sum(queue_sizes) / len(queue_sizes) if queue_sizes else 0,
                "p95_size": percentile(queue_sizes, 95)
            },
            "topics": {
                "letter_messages": sum(letter_topics.values()),
                "border_messages": sum(border_topics.values()),  
                "nfc_messages": sum(nfc_topics.values()),
                "total_topics": len(self.topic_message_counts)
            },
            "connection": {
                "failures": self.connection_failures,
                "reconnections": self.reconnection_count,
                "last_connect_ago_ms": (now - self.last_connection_time * 1000) if self.last_connection_time else None
            },
            "retained_breakdown": dict(self.topic_retained_counts)
        }

class MqttLatencyTester:
    """Sends periodic echo messages to measure broker roundtrip latency"""
    
    def __init__(self, publish_queue: asyncio.Queue, metrics: MqttMetrics):
        self.publish_queue = publish_queue
        self.metrics = metrics
        self.test_interval_s = 5.0  # Send test message every 5 seconds
        self.running = False
    
    async def start_testing(self):
        """Start sending periodic latency test messages"""
        self.running = True
        echo_counter = 0
        
        while self.running:
            try:
                echo_id = f"{int(time.time())}_{echo_counter}"
                now_ms = time.time() * 1000
                
                # Send echo message (non-retained)
                await self.publish_queue.put((f"test/echo/{echo_id}", "ping", False, now_ms))
                echo_counter += 1
                
                await asyncio.sleep(self.test_interval_s)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Latency tester error: {e}")
                await asyncio.sleep(1)
    
    def stop_testing(self):
        """Stop sending test messages"""
        self.running = False

class MqttMetricsLogger:
    """Logs metrics to file for analysis"""
    
    def __init__(self, metrics: MqttMetrics, log_file: str = "mqtt_metrics.jsonl"):
        self.metrics = metrics
        self.log_file = log_file
        self.log_interval_s = 10.0  # Log stats every 10 seconds
        self.running = False
    
    async def start_logging(self):
        """Start periodic metrics logging"""
        self.running = True
        
        with open(self.log_file, "w") as f:  # Clear existing log
            pass
            
        while self.running:
            try:
                stats = self.metrics.get_stats()
                
                with open(self.log_file, "a") as f:
                    f.write(json.dumps(stats) + "\n")
                
                # Also log summary to console
                msg = stats["messages"]
                latency = stats["latency_ms"]
                queue = stats["queue"]
                
                logging.info(f"MQTT Metrics - Messages: {msg['published_total']} "
                           f"({msg['retention_rate']:.1%} retained), "
                           f"Queue: {queue['current_size']}/{queue['max_size']}, "
                           f"Latency p95: {latency['roundtrip_p95']:.1f}ms")
                
                await asyncio.sleep(self.log_interval_s)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Metrics logger error: {e}")
                await asyncio.sleep(1)
    
    def stop_logging(self):
        """Stop metrics logging"""
        self.running = False

# Global metrics instance
mqtt_metrics = MqttMetrics()