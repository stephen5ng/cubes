# Cube Responsiveness Test Summary

## Results Comparison

| Test | Optimization | Duration | Max Response | Avg Response | Recovery Time | Grade | Status | Improvement |
|------|------------|----------|-------------|-------------|---------------|--------|--------|------------|
| **sng** | Baseline | 11.3s | 11.4s | 2.6s | 0.5s | 🟡 FAIR | ❌ FAIL | - |
| **sng** | Border Non-Retained (Fixed) | 9.8s | 10.6s | 2.5s | 1.9s | 🟡 FAIR | ❌ FAIL | ✅ 7.0% faster max response |
| **sng** | NFC Reset Removed from loop() (Previous) | 20.3s | 4.6s | 0.7s | 0.6s | 🟢 GOOD | ✅ PASS | ✅ Max -60%, Avg -73% vs baseline |
| **sng** | NFC Reset + NFC Throttling (20Hz) | 10.0s | 1.56s | 0.31s | 0.2s | ✅ EXCELLENT | ✅ PASS | ✅ Max -86%, Avg -88% vs baseline |
| **sng** | MQTT-aware Display Throttle (50ms) | 9.8s | 0.80s | 0.20s | 0.0s | ✅ EXCELLENT | ✅ PASS | ✅ Max -93%, Avg -92% vs baseline |
| **stress_0.1** | Baseline | 13.8s | 81.4s | 38.8s | 2.9s | 🔴 POOR | ❌ FAIL | - |
| **stress_0.1** | Border Non-Retained (Fixed) | 13.6s | 79.6s | 37.6s | 3.0s | 🔴 POOR | ❌ FAIL | ✅ 2.2% faster max response |
| **stress_0.1** | NFC Reset + NFC Throttling (20Hz) | 14.2s | 25.8s | 4.16s | 0.5s | 🟡 FAIR | ❌ FAIL | ✅ Max -68%, Avg -89% vs baseline |
| **stress_0.1** | MQTT-aware Display Throttle (50ms) | 14.1s | 20.54s | 2.74s | 0.1s | 🟡 FAIR | ❌ FAIL | ✅ Max -75%, Avg -93% vs baseline |

## Key Insights:

 - MQTT-aware display throttle prioritizes draining MQTT bursts by skipping display updates for ~50ms after recent activity.
 - Effect: SNG now EXCELLENT (avg ~204ms). On stress_0.1, backlog clears quickly (first-half avg ~5.39s → second-half avg ~0.21s).

### 🟡 SNG Test (Short workload):
- **Baseline problem**: Even a short 11-second test created an 11.4-second backlog
- **Impact**: Cube unresponsive for ~11 seconds after test completion
- **Improvement**: Removing NFC reset from `loop()` reduced max to ~4.6s and avg to ~0.7s, passing the test
- **Recovery**: Quick recovery once backlog cleared (~0.6s after fix)

### 🔴 STRESS_0.1 Test (Medium workload):
- **Problem**: 13.8-second test creates a massive 81.4-second message backlog  
- **Impact**: Cube severely overloaded for over 1 minute after test
- **Pattern**: Clear linear backlog processing (81s → 82ms over time)

## Root Cause Analysis:

1. **Message Accumulation**: Tests generate more messages than cubes can process in real-time
2. **FIFO Queue Processing**: Cubes process messages in strict order, causing linear backlog reduction
3. **Network vs Processing**: Issue exists even with real broker (not just localhost), indicating cube-side processing bottleneck

## Optimization Targets:

1. **Primary**: Reduce total message volume during tests
2. **Secondary**: Optimize message processing efficiency on ESP32
3. **Tertiary**: Implement message prioritization (if possible)

## Next Steps:

Use this baseline to validate improvements. Success criteria:
- **Target**: Max response time < 1000ms, Avg response time < 500ms
- **Acceptable**: Max response time < 5000ms, Avg response time < 1000ms  
- **Goal**: Pass responsiveness test (Grade: 🟢 GOOD or better)

---

*Generated: 2025-08-13*