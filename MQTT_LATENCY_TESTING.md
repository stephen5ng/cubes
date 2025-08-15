# MQTT Latency Testing & Non-Retained Migration Plan

## Overview

This plan helps diagnose MQTT latency issues and migrate away from retained messages to reduce broker load.

## Theory

**Suspected Issue**: MQTT broker is overloaded with retained messages, causing queuing delays and latency spikes.

**Solution**: Reduce or eliminate retained messages so missed messages are dropped instead of queued, reducing broker memory usage and improving throughput.

## Phase 1: Measure Current Performance

### 1. Start Echo Responder (for latency measurement)

```bash
# In terminal 1
python3 mqtt_echo_responder.py
```

### 2. Run Your Game with Metrics

```bash
# In terminal 2  
python3 main.py --tags tag_ids.txt
```

This will:
- Collect MQTT metrics in `mqtt_metrics.jsonl`
- Measure roundtrip latency every 5 seconds
- Log queue sizes and message volume
- Track retained vs non-retained message ratios

### 3. Analyze Baseline Metrics

After running for a while, check:

```bash
# View latest metrics
tail mqtt_metrics.jsonl | jq '.'

# Key metrics to watch:
# - retention_rate: What % of messages are retained
# - roundtrip_p95: 95th percentile latency in ms  
# - max_queue_size: Peak publish queue size
# - topic breakdown: Which topics send most messages
```

Expected findings:
- High retention rate (>80% retained messages)
- Growing queue sizes during active gameplay
- Higher latency during message bursts

## Phase 2: Test Migration Strategies

### Strategy Testing

Test different levels of retained message reduction:

```bash
# Test conservative approach (only flash messages non-retained)
python3 test_mqtt_migration.py --strategy conservative --duration 60

# Test moderate approach (flash + NFC non-retained)
python3 test_mqtt_migration.py --strategy moderate --duration 60

# Test aggressive approach (only letters retained)
python3 test_mqtt_migration.py --strategy aggressive --duration 60

# Test full non-retained
python3 test_mqtt_migration.py --strategy full --duration 60

# Compare all strategies
python3 test_mqtt_migration.py --compare --duration 30
```

### Expected Results

| Strategy | Retention Rate | Queue Size | Latency | Trade-offs |
|----------|---------------|------------|---------|------------|
| Current | ~90% | High | High | Reliable state |
| Conservative | ~85% | Medium | Medium | Minimal risk |
| Moderate | ~70% | Low | Low | Good balance |
| Aggressive | ~30% | Very Low | Very Low | State sync needed |
| Full | 0% | Minimal | Minimal | Requires robust sync |

## Phase 3: Implement Chosen Strategy

Based on test results, implement the best strategy:

### Option A: Moderate Strategy (Recommended)

```python
# In main.py, add after creating publish_queue:
from non_retained_mqtt import migrate_to_non_retained, MIGRATION_STRATEGIES

# Apply moderate strategy
non_retained_manager = await migrate_to_non_retained(
    publish_queue, cube_managers, MIGRATION_STRATEGIES["moderate"]
)
```

### Option B: Aggressive Strategy (If moderate isn't enough)

```python
# Same as above but with "aggressive" strategy
non_retained_manager = await migrate_to_non_retained(
    publish_queue, cube_managers, MIGRATION_STRATEGIES["aggressive"]
)

# Start periodic sync for reliability
sync_tasks = await non_retained_manager.start_services()
```

## Phase 4: Validate Improvements

### A/B Testing

1. **Run baseline** (current system) for 10 minutes, save metrics
2. **Run with chosen strategy** for 10 minutes, save metrics  
3. **Compare**:
   - Message latency (expect 50-80% reduction)
   - Queue sizes (expect 60-90% reduction)
   - Game responsiveness (subjective)
   - Any state synchronization issues

### Key Metrics to Track

```bash
# Before and after comparison
echo "BEFORE (retained messages):"
cat baseline_mqtt_metrics.jsonl | tail -1 | jq '.latency_ms.roundtrip_p95'

echo "AFTER (non-retained strategy):" 
cat mqtt_metrics.jsonl | tail -1 | jq '.latency_ms.roundtrip_p95'
```

### Rollback Plan

If issues arise:
1. Comment out non-retained migration code
2. Restart game - returns to full retained mode
3. Debug issues with sync logic

## Message Type Analysis

### Current Retained Usage

| Message Type | Frequency | Retention Needed? | Migration Priority |
|--------------|-----------|-------------------|-------------------|
| `cube/*/letter` | High | Yes (state critical) | Low |
| `cube/*/border_*` | Very High | Medium (visual only) | High |
| `cube/*/lock` | Low | Medium (UX) | Medium |
| `game/nfc/*` | Medium | No (events) | High |
| `cube/*/flash` | Low | No (effects) | Already done |

### Recommended Migration Order

1. **Phase 1**: `cube/*/flash` (already non-retained)
2. **Phase 2**: `game/nfc/*` (events don't need retention)  
3. **Phase 3**: `cube/*/border_*` (visual, can be re-synced)
4. **Phase 4**: `cube/*/lock` (UX, brief duration)
5. **Phase 5**: `cube/*/letter` (only if needed, requires robust sync)

## Expected Performance Gains

Based on your current usage patterns:

- **Queue size reduction**: 70-90% (from retained message accumulation)
- **Latency reduction**: 50-80% (from reduced broker load)
- **Memory usage**: 60-80% reduction on broker
- **Throughput increase**: 2-3x during peak load

## Monitoring & Alerting

Add ongoing monitoring:

```bash
# Watch metrics in real-time
tail -f mqtt_metrics.jsonl | jq '.queue.current_size, .latency_ms.roundtrip_p95'

# Alert if latency exceeds threshold
python3 -c "
import json
with open('mqtt_metrics.jsonl') as f:
    latest = json.loads(f.readlines()[-1])
    latency = latest['latency_ms']['roundtrip_p95']
    if latency > 100:  # 100ms threshold
        print(f'ALERT: High latency {latency}ms')
"
```

## Files Created

- `mqtt_metrics.py` - Metrics collection system
- `mqtt_echo_responder.py` - Latency measurement service  
- `non_retained_mqtt.py` - Non-retained architecture
- `test_mqtt_migration.py` - Strategy testing framework
- `MQTT_LATENCY_TESTING.md` - This guide

## Next Steps

1. **Start with baseline measurement** - run echo responder + game with metrics
2. **Analyze current performance** - identify bottlenecks  
3. **Test migration strategies** - find optimal balance
4. **Implement chosen strategy** - with rollback plan
5. **Validate improvements** - measure gains
6. **Monitor ongoing** - prevent regressions