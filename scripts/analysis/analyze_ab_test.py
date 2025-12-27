#!/usr/bin/env python3
"""
A/B Test Analysis: BEFORE vs AFTER Emergency MQTT Fix

Compares the identical stress_0.1 test run with and without the emergency fix.
"""

import json

def analyze_metrics(before_file, after_file):
    """Analyze and compare BEFORE vs AFTER metrics"""
    
    # Read the last line (final metrics) from each file
    with open(before_file, 'r') as f:
        before_lines = f.readlines()
        before_final = json.loads(before_lines[-1])
    
    with open(after_file, 'r') as f:
        after_lines = f.readlines()
        after_final = json.loads(after_lines[-1])
    
    print("🧪 CONTROLLED A/B TEST RESULTS")
    print("=" * 50)
    print("Same test (stress_0.1) run with identical conditions")
    print()
    
    # Key metrics comparison
    before_msgs = before_final["messages"]
    after_msgs = after_final["messages"]
    before_queue = before_final["queue"]
    after_queue = after_final["queue"]
    
    print("📊 MESSAGE METRICS")
    print("-" * 30)
    
    print(f"{'Metric':<20} {'BEFORE':<15} {'AFTER':<15} {'Change':<15}")
    print("-" * 65)
    
    # Total messages
    before_total = before_msgs["published_total"]
    after_total = after_msgs["published_total"]
    total_change = f"{((after_total - before_total) / before_total * 100):+.1f}%" if before_total else "N/A"
    print(f"{'Total Messages':<20} {before_total:<15} {after_total:<15} {total_change:<15}")
    
    # Retained messages
    before_retained = before_msgs["published_retained"] 
    after_retained = after_msgs["published_retained"]
    retained_change = f"{((after_retained - before_retained) / before_retained * 100):+.1f}%" if before_retained else "N/A"
    print(f"{'Retained Msgs':<20} {before_retained:<15} {after_retained:<15} {retained_change:<15}")
    
    # Retention rate
    before_rate = before_msgs["retention_rate"] * 100
    after_rate = after_msgs["retention_rate"] * 100
    rate_change = f"{(after_rate - before_rate):+.1f}%"
    print(f"{'Retention Rate':<20} {before_rate:.1f}%{'':<10} {after_rate:.1f}%{'':<10} {rate_change:<15}")
    
    print()
    print("🗄️ QUEUE METRICS") 
    print("-" * 30)
    
    # Queue sizes
    before_max_queue = before_queue["max_size"]
    after_max_queue = after_queue["max_size"]
    queue_change = f"{((after_max_queue - before_max_queue) / before_max_queue * 100):+.1f}%" if before_max_queue else "N/A"
    print(f"{'Max Queue Size':<20} {before_max_queue:<15} {after_max_queue:<15} {queue_change:<15}")
    
    before_avg_queue = before_queue["avg_size"]
    after_avg_queue = after_queue["avg_size"] 
    avg_queue_change = f"{((after_avg_queue - before_avg_queue) / before_avg_queue * 100):+.1f}%" if before_avg_queue else "N/A"
    print(f"{'Avg Queue Size':<20} {before_avg_queue:<15.0f} {after_avg_queue:<15.0f} {avg_queue_change:<15}")
    
    print()
    print("📈 KEY IMPROVEMENTS")
    print("-" * 30)
    
    # Calculate key improvements
    retention_improvement = before_rate - after_rate
    queue_improvement = ((before_max_queue - after_max_queue) / before_max_queue * 100) if before_max_queue else 0
    
    print(f"✅ Retention Rate Reduced: {retention_improvement:.1f} percentage points")
    print(f"✅ Max Queue Size Reduced: {queue_improvement:.1f}%")
    
    # NFC message analysis
    before_nfc = sum(v for k, v in before_final["retained_breakdown"].items() if "game/nfc/" in k)
    after_nfc = sum(v for k, v in after_final["retained_breakdown"].items() if "game/nfc/" in k)
    
    print(f"✅ NFC Messages Retained: {before_nfc} → {after_nfc} ({after_nfc - before_nfc:+d})")
    
    print()
    print("🎯 SUMMARY")
    print("-" * 30)
    
    if retention_improvement > 5:
        print("🟢 SIGNIFICANT retention rate improvement")
    elif retention_improvement > 0:
        print("🟡 MODERATE retention rate improvement") 
    else:
        print("🔴 NO retention rate improvement")
        
    if queue_improvement > 10:
        print("🟢 SIGNIFICANT queue size reduction")
    elif queue_improvement > 0:
        print("🟡 MODERATE queue size reduction")
    else:
        print("🔴 NO queue size improvement")
    
    # Detailed topic breakdown
    print()
    print("📋 DETAILED TOPIC ANALYSIS")
    print("-" * 30)
    
    before_topics = before_final["topics"]
    after_topics = after_final["topics"] 
    
    print(f"{'Topic Type':<15} {'BEFORE':<10} {'AFTER':<10} {'Change':<10}")
    print("-" * 45)
    print(f"{'Letter Msgs':<15} {before_topics['letter_messages']:<10} {after_topics['letter_messages']:<10} {after_topics['letter_messages'] - before_topics['letter_messages']:+d}")
    print(f"{'Border Msgs':<15} {before_topics['border_messages']:<10} {after_topics['border_messages']:<10} {after_topics['border_messages'] - before_topics['border_messages']:+d}")  
    print(f"{'NFC Msgs':<15} {before_topics['nfc_messages']:<10} {after_topics['nfc_messages']:<10} {after_topics['nfc_messages'] - before_topics['nfc_messages']:+d}")

if __name__ == "__main__":
    analyze_metrics("mqtt_metrics_BEFORE.jsonl", "mqtt_metrics_AFTER.jsonl")