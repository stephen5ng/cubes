# Cube Responsiveness Test Results

Baseline measurements before any MQTT optimizations.

## Test: sng (Wed Aug 13 11:08:44 PDT 2025)

[2025-08-13 11:08:47] [RGBME] [INFO]: RGBME v0.12.2 - 192x256 Matrix | 1x1 Chain | 4px per LED (CIRCLE) | BrowserAdapter
[2025-08-13 11:08:47] [RGBME] [INFO]: Starting server...
[2025-08-13 11:08:47] [RGBME] [INFO]: Server started and ready to accept requests on http://localhost:8888/
pygame-ce 2.5.2 (SDL 2.30.8, Python 3.13.1)
STARTING LOGGING output/output.publish.jsonl
STARTING LOGGING None
all_cubes: {'5', '6', '3', '1', '4', '2'}, reported_cubes: set()
Player 0: Still waiting for neighbor reports from cubes: {'5', '6', '3', '4', '1', '2'}
all_cubes: {'7', '11', '8', '10', '12', '9'}, reported_cubes: set()
Player 1: Still waiting for neighbor reports from cubes: {'11', '8', '10', '12', '7', '9'}
joystick count: 0
STARTING LOGGING output/output.jsonl
starting due to ESC
=========start_game KeyboardInput 1559
1559 starting new game with input_device: KeyboardInput
ADDED KeyboardInput in self.input_devices: True
start_cubes: starting letter 1559
>>>>>>>> app.STARTING
initial bingo: ---------- JURIES --------
>>>>>>>> app.STARTED
start done
asyncio main done
🚀 CUBE RESPONSIVENESS TEST
Test: sng
Broker: 192.168.8.247
============================================================
🧪 Running functional test: sng
============================================================

✅ Test completed in 11.3s with return code: 0

⏱️  Starting responsiveness measurement in 3 seconds...

🔍 Measuring cube 1 responsiveness
============================================================
🔍 Starting post-test ping monitoring for cube 1
📊 Will ping every 1s for 30s
📡 Broker: 192.168.8.247

📤 Sent ping 1: ping_1_1755108539628
📤 Sent ping 2: ping_2_1755108540629
📤 Sent ping 3: ping_3_1755108541631
📤 Sent ping 4: ping_4_1755108542633
📤 Sent ping 5: ping_5_1755108543635
📤 Sent ping 6: ping_6_1755108544637
📤 Sent ping 7: ping_7_1755108545640
📤 Sent ping 8: ping_8_1755108546643
📤 Sent ping 9: ping_9_1755108547645
📤 Sent ping 10: ping_10_1755108548647
📤 Sent ping 11: ping_11_1755108549649
📤 Sent ping 12: ping_12_1755108550651
📥 Response: ping_1_1755108539628 -> 11416.1ms
📥 Response: ping_2_1755108540629 -> 10462.0ms
📥 Response: ping_3_1755108541631 -> 9669.7ms
📥 Response: ping_4_1755108542633 -> 8676.9ms
📥 Response: ping_5_1755108543635 -> 7675.3ms
📥 Response: ping_6_1755108544637 -> 6672.8ms
📥 Response: ping_7_1755108545640 -> 5674.9ms
📥 Response: ping_8_1755108546643 -> 4727.0ms
📥 Response: ping_9_1755108547645 -> 3917.8ms
📥 Response: ping_10_1755108548647 -> 2922.9ms
📥 Response: ping_11_1755108549649 -> 1921.2ms
📥 Response: ping_12_1755108550651 -> 919.5ms
📤 Sent ping 13: ping_13_1755108551653
📥 Response: ping_13_1755108551653 -> 192.2ms
📤 Sent ping 14: ping_14_1755108552655
📥 Response: ping_14_1755108552655 -> 315.7ms
📤 Sent ping 15: ping_15_1755108553658
📥 Response: ping_15_1755108553658 -> 254.5ms
📤 Sent ping 16: ping_16_1755108554661
📥 Response: ping_16_1755108554661 -> 305.0ms
📤 Sent ping 17: ping_17_1755108555662
📥 Response: ping_17_1755108555662 -> 221.8ms
📤 Sent ping 18: ping_18_1755108556665
📥 Response: ping_18_1755108556665 -> 319.2ms
📤 Sent ping 19: ping_19_1755108557667
📥 Response: ping_19_1755108557667 -> 34.5ms
📤 Sent ping 20: ping_20_1755108558669
📥 Response: ping_20_1755108558669 -> 72.8ms
📤 Sent ping 21: ping_21_1755108559670
📥 Response: ping_21_1755108559670 -> 104.2ms
📤 Sent ping 22: ping_22_1755108560673
📥 Response: ping_22_1755108560673 -> 132.9ms
📤 Sent ping 23: ping_23_1755108561675
📥 Response: ping_23_1755108561675 -> 163.4ms
📤 Sent ping 24: ping_24_1755108562678
📥 Response: ping_24_1755108562678 -> 184.8ms
📤 Sent ping 25: ping_25_1755108563680
📥 Response: ping_25_1755108563680 -> 179.8ms
📤 Sent ping 26: ping_26_1755108564681
📥 Response: ping_26_1755108564681 -> 215.9ms
📤 Sent ping 27: ping_27_1755108565684
📥 Response: ping_27_1755108565684 -> 234.1ms
📤 Sent ping 28: ping_28_1755108566690
📥 Response: ping_28_1755108566690 -> 251.4ms
📤 Sent ping 29: ping_29_1755108567692
📥 Response: ping_29_1755108567692 -> 84.4ms
📤 Sent ping 30: ping_30_1755108568694
📥 Response: ping_30_1755108568694 -> 104.5ms

⏳ Waiting 5s for final responses...

============================================================
📊 POST-TEST PING ANALYSIS
============================================================
📈 Response Statistics:
   Responses received: 30/30 (100.0%)
   Average response time: 2600.9ms
   Min response time: 34.5ms
   Max response time: 11416.1ms

📉 Trend Analysis:
   First half average: 5027.9ms
   Second half average: 173.9ms
   ✅ IMPROVING: Response times decreased by 96.5%
      → Cube appears to be catching up with backlog

🚦 Response Time Categories:
   Fast (<100ms): 3 (10.0%)
   Normal (100-1000ms): 16 (53.3%)
   Slow (≥1000ms): 11 (36.7%)
   ⚠️  11 slow responses indicate backlog processing

💾 Detailed results saved to: post_test_ping_results.json

🎯 RESPONSIVENESS TEST RESULTS
============================================================
Response Rate: 100.0%
Average Response: 2600.9ms
Max Response: 11416.1ms
Recovery Time: 0.5s

Grade: 🟡 FAIR
Assessment: Moderate backlog - room for improvement

📊 FINAL SUMMARY
============================================================
❌ FAIL: Cube responsiveness below acceptable thresholds
Consider MQTT performance optimizations

---

## Test: stress_0.1 (Wed Aug 13 11:09:49 PDT 2025)

[2025-08-13 11:09:50] [RGBME] [INFO]: RGBME v0.12.2 - 192x256 Matrix | 1x1 Chain | 4px per LED (CIRCLE) | BrowserAdapter
[2025-08-13 11:09:50] [RGBME] [INFO]: Starting server...
[2025-08-13 11:09:50] [RGBME] [INFO]: Server started and ready to accept requests on http://localhost:8888/
pygame-ce 2.5.2 (SDL 2.30.8, Python 3.13.1)
STARTING LOGGING output/output.publish.jsonl
STARTING LOGGING None
all_cubes: {'2', '4', '1', '6', '5', '3'}, reported_cubes: set()
Player 0: Still waiting for neighbor reports from cubes: {'5', '2', '4', '6', '3', '1'}
all_cubes: {'7', '8', '11', '10', '9', '12'}, reported_cubes: set()
Player 1: Still waiting for neighbor reports from cubes: {'7', '8', '11', '10', '9', '12'}
joystick count: 0
STARTING LOGGING output/output.jsonl
all_cubes: {'2', '4', '1', '6', '5', '3'}, reported_cubes: {'2', '4', '1', '6', '5', '3'}
all cubes have neighbors
ABC start sequence activated: {'A': '1', 'B': '2', 'C': '3'}
manager.cube_chain: {'1': '2'}
manager.cube_chain: {}
manager.cube_chain: {'1': '2', '2': '3'}
starting from callback
all_cubes: {'2', '4', '1', '6', '5', '3'}, reported_cubes: {'2', '4', '1', '6', '5', '3'}
all cubes have neighbors
ABC start sequence activated: {'A': '1', 'B': '3', 'C': '4'}
898 starting new game with input_device: CubesInput
ADDED CubesInput in self.input_devices: True
start_cubes: starting letter 898
>>>>>>>> app.STARTING
initial bingo: ---------- ATTIRE --------
>>>>>>>> app.STARTED
start done
asyncio main done
🚀 CUBE RESPONSIVENESS TEST
Test: stress_0.1
Broker: 192.168.8.247
============================================================
🧪 Running functional test: stress_0.1
============================================================

✅ Test completed in 13.8s with return code: 0

⏱️  Starting responsiveness measurement in 3 seconds...

🔍 Measuring cube 1 responsiveness
============================================================
🔍 Starting post-test ping monitoring for cube 1
📊 Will ping every 2s for 90s
📡 Broker: 192.168.8.247

📤 Sent ping 1: ping_1_1755108606780
📤 Sent ping 2: ping_2_1755108608782
📤 Sent ping 3: ping_3_1755108610783
📤 Sent ping 4: ping_4_1755108612785
📤 Sent ping 5: ping_5_1755108614786
📤 Sent ping 6: ping_6_1755108616789
📤 Sent ping 7: ping_7_1755108618790
📤 Sent ping 8: ping_8_1755108620792
📤 Sent ping 9: ping_9_1755108622793
📤 Sent ping 10: ping_10_1755108624795
📤 Sent ping 11: ping_11_1755108626797
📤 Sent ping 12: ping_12_1755108628798
📤 Sent ping 13: ping_13_1755108630800
📤 Sent ping 14: ping_14_1755108632801
📤 Sent ping 15: ping_15_1755108634807
📤 Sent ping 16: ping_16_1755108636809
📤 Sent ping 17: ping_17_1755108638811
📤 Sent ping 18: ping_18_1755108640814
📤 Sent ping 19: ping_19_1755108642816
📤 Sent ping 20: ping_20_1755108644819
📤 Sent ping 21: ping_21_1755108646824
📤 Sent ping 22: ping_22_1755108648825
📤 Sent ping 23: ping_23_1755108650825
📤 Sent ping 24: ping_24_1755108652826
📤 Sent ping 25: ping_25_1755108654829
📤 Sent ping 26: ping_26_1755108656832
📤 Sent ping 27: ping_27_1755108658839
📤 Sent ping 28: ping_28_1755108660841
📤 Sent ping 29: ping_29_1755108662843
📤 Sent ping 30: ping_30_1755108664850
📤 Sent ping 31: ping_31_1755108666852
📤 Sent ping 32: ping_32_1755108668854
📤 Sent ping 33: ping_33_1755108670855
📤 Sent ping 34: ping_34_1755108672857
📤 Sent ping 35: ping_35_1755108674859
📤 Sent ping 36: ping_36_1755108676861
📤 Sent ping 37: ping_37_1755108678863
📤 Sent ping 38: ping_38_1755108680865
📤 Sent ping 39: ping_39_1755108682868
📤 Sent ping 40: ping_40_1755108684870
📤 Sent ping 41: ping_41_1755108686874
📥 Response: ping_1_1755108606780 -> 81383.8ms
📥 Response: ping_2_1755108608782 -> 79393.7ms
📥 Response: ping_3_1755108610783 -> 77409.4ms
📥 Response: ping_4_1755108612785 -> 75460.8ms
📥 Response: ping_5_1755108614786 -> 73524.7ms
📥 Response: ping_6_1755108616789 -> 71550.5ms
📥 Response: ping_7_1755108618790 -> 69619.9ms
📥 Response: ping_8_1755108620792 -> 67654.2ms
📥 Response: ping_9_1755108622793 -> 65719.6ms
📥 Response: ping_10_1755108624795 -> 63767.4ms
📥 Response: ping_11_1755108626797 -> 61816.7ms
📥 Response: ping_12_1755108628798 -> 59861.3ms
📥 Response: ping_13_1755108630800 -> 57914.2ms
📥 Response: ping_14_1755108632801 -> 55956.5ms
📥 Response: ping_15_1755108634807 -> 53999.1ms
📥 Response: ping_16_1755108636809 -> 52044.4ms
📤 Sent ping 42: ping_42_1755108688879
📥 Response: ping_17_1755108638811 -> 50089.5ms
📥 Response: ping_18_1755108640814 -> 48136.3ms
📥 Response: ping_19_1755108642816 -> 46185.1ms
📥 Response: ping_20_1755108644819 -> 44216.3ms
📥 Response: ping_21_1755108646824 -> 42262.8ms
📥 Response: ping_22_1755108648825 -> 40309.6ms
📥 Response: ping_23_1755108650825 -> 38354.2ms
📥 Response: ping_24_1755108652826 -> 36403.2ms
📥 Response: ping_25_1755108654829 -> 34451.4ms
📥 Response: ping_26_1755108656832 -> 32484.2ms
📥 Response: ping_27_1755108658839 -> 30522.9ms
📥 Response: ping_28_1755108660841 -> 28571.8ms
📥 Response: ping_29_1755108662843 -> 26615.3ms
📥 Response: ping_30_1755108664850 -> 24950.2ms
📥 Response: ping_31_1755108666852 -> 23972.8ms
📥 Response: ping_32_1755108668854 -> 21995.6ms
📥 Response: ping_33_1755108670855 -> 19994.3ms
📥 Response: ping_34_1755108672857 -> 17992.3ms
📥 Response: ping_35_1755108674859 -> 15991.0ms
📥 Response: ping_36_1755108676861 -> 13988.9ms
📥 Response: ping_37_1755108678863 -> 11987.1ms
📥 Response: ping_38_1755108680865 -> 9985.0ms
📥 Response: ping_39_1755108682868 -> 7982.3ms
📥 Response: ping_40_1755108684870 -> 5980.9ms
📥 Response: ping_41_1755108686874 -> 3976.9ms
📥 Response: ping_42_1755108688879 -> 1972.1ms
📤 Sent ping 43: ping_43_1755108690882
📥 Response: ping_43_1755108690882 -> 182.5ms
📤 Sent ping 44: ping_44_1755108692883
📥 Response: ping_44_1755108692883 -> 235.6ms
📤 Sent ping 45: ping_45_1755108694884
📥 Response: ping_45_1755108694884 -> 82.6ms

⏳ Waiting 5s for final responses...

============================================================
📊 POST-TEST PING ANALYSIS
============================================================
📈 Response Statistics:
   Responses received: 45/45 (100.0%)
   Average response time: 38821.1ms
   Min response time: 82.6ms
   Max response time: 81383.8ms

📉 Trend Analysis:
   First half average: 60830.7ms
   Second half average: 17768.4ms
   ✅ IMPROVING: Response times decreased by 70.8%
      → Cube appears to be catching up with backlog

🚦 Response Time Categories:
   Fast (<100ms): 1 (2.2%)
   Normal (100-1000ms): 2 (4.4%)
   Slow (≥1000ms): 42 (93.3%)
   ⚠️  42 slow responses indicate backlog processing

💾 Detailed results saved to: post_test_ping_results.json

🎯 RESPONSIVENESS TEST RESULTS
============================================================
Response Rate: 100.0%
Average Response: 38821.1ms
Max Response: 81383.8ms
Recovery Time: 2.9s

Grade: 🔴 POOR
Assessment: High latency indicates significant message backlog

📊 FINAL SUMMARY
============================================================
❌ FAIL: Cube responsiveness below acceptable thresholds
Consider MQTT performance optimizations
## Border Messages Non-Retained Test (Wed Aug 13 11:17:49 PDT 2025)

[2025-08-13 11:17:50] [RGBME] [INFO]: RGBME v0.12.2 - 192x256 Matrix | 1x1 Chain | 4px per LED (CIRCLE) | BrowserAdapter
[2025-08-13 11:17:50] [RGBME] [INFO]: Starting server...
[2025-08-13 11:17:50] [RGBME] [INFO]: Server started and ready to accept requests on http://localhost:8888/
pygame-ce 2.5.2 (SDL 2.30.8, Python 3.13.1)
STARTING LOGGING output/output.publish.jsonl
STARTING LOGGING None
all_cubes: {'2', '6', '5', '3', '4', '1'}, reported_cubes: set()
Player 0: Still waiting for neighbor reports from cubes: {'2', '5', '3', '4', '1', '6'}
all_cubes: {'9', '10', '11', '12', '7', '8'}, reported_cubes: set()
Player 1: Still waiting for neighbor reports from cubes: {'9', '7', '8', '10', '11', '12'}
joystick count: 0
STARTING LOGGING output/output.jsonl
starting due to ESC
=========start_game KeyboardInput 1559
1559 starting new game with input_device: KeyboardInput
ADDED KeyboardInput in self.input_devices: True
start_cubes: starting letter 1559
>>>>>>>> app.STARTING
initial bingo: ---------- JURIES --------
>>>>>>>> app.STARTED
start done
asyncio main done
🚀 CUBE RESPONSIVENESS TEST
Test: sng
Broker: 192.168.8.247
============================================================
🧪 Running functional test: sng
============================================================

✅ Test completed in 9.6s with return code: 0

⏱️  Starting responsiveness measurement in 3 seconds...

🔍 Measuring cube 1 responsiveness
============================================================
🔍 Starting post-test ping monitoring for cube 1
📊 Will ping every 1s for 30s
📡 Broker: 192.168.8.247

📤 Sent ping 1: ping_1_1755109082298
📤 Sent ping 2: ping_2_1755109083300
📤 Sent ping 3: ping_3_1755109084303
📤 Sent ping 4: ping_4_1755109085305
📤 Sent ping 5: ping_5_1755109086307
📤 Sent ping 6: ping_6_1755109087309
📤 Sent ping 7: ping_7_1755109088312
📤 Sent ping 8: ping_8_1755109089314
📤 Sent ping 9: ping_9_1755109090316
📤 Sent ping 10: ping_10_1755109091318
📤 Sent ping 11: ping_11_1755109092320
📥 Response: ping_1_1755109082298 -> 10658.1ms
📥 Response: ping_2_1755109083300 -> 9669.1ms
📥 Response: ping_3_1755109084303 -> 8666.5ms
📥 Response: ping_4_1755109085305 -> 7712.8ms
📥 Response: ping_5_1755109086307 -> 6910.1ms
📥 Response: ping_6_1755109087309 -> 5912.8ms
📥 Response: ping_7_1755109088312 -> 4910.5ms
📥 Response: ping_8_1755109089314 -> 3933.1ms
📥 Response: ping_9_1755109090316 -> 2987.3ms
📤 Sent ping 12: ping_12_1755109093322
📥 Response: ping_10_1755109091318 -> 2154.3ms
📥 Response: ping_11_1755109092320 -> 1166.5ms
📥 Response: ping_12_1755109093322 -> 426.4ms
📤 Sent ping 13: ping_13_1755109094324
📥 Response: ping_13_1755109094324 -> 202.7ms
📤 Sent ping 14: ping_14_1755109095326
📥 Response: ping_14_1755109095326 -> 238.4ms
📤 Sent ping 15: ping_15_1755109096330
📥 Response: ping_15_1755109096330 -> 666.1ms
📤 Sent ping 16: ping_16_1755109097337
📥 Response: ping_16_1755109097337 -> 269.1ms
📤 Sent ping 17: ping_17_1755109098339
📥 Response: ping_17_1755109098339 -> 60.5ms
📤 Sent ping 18: ping_18_1755109099341
📥 Response: ping_18_1755109099341 -> 82.5ms
📤 Sent ping 19: ping_19_1755109100342
📥 Response: ping_19_1755109100342 -> 110.8ms
📤 Sent ping 20: ping_20_1755109101344
📥 Response: ping_20_1755109101344 -> 195.2ms
📤 Sent ping 21: ping_21_1755109102348
📥 Response: ping_21_1755109102348 -> 173.9ms
📤 Sent ping 22: ping_22_1755109103350
📥 Response: ping_22_1755109103350 -> 156.2ms
📤 Sent ping 23: ping_23_1755109104352
📥 Response: ping_23_1755109104352 -> 185.7ms
📤 Sent ping 24: ping_24_1755109105355
📥 Response: ping_24_1755109105355 -> 217.7ms
📤 Sent ping 25: ping_25_1755109106358
📥 Response: ping_25_1755109106358 -> 239.7ms
📤 Sent ping 26: ping_26_1755109107360
📥 Response: ping_26_1755109107360 -> 268.2ms
📤 Sent ping 27: ping_27_1755109108362
📥 Response: ping_27_1755109108362 -> 212.9ms
📤 Sent ping 28: ping_28_1755109109364
📥 Response: ping_28_1755109109364 -> 94.7ms
📤 Sent ping 29: ping_29_1755109110366
📥 Response: ping_29_1755109110366 -> 116.8ms
📤 Sent ping 30: ping_30_1755109111369
📥 Response: ping_30_1755109111369 -> 153.6ms

⏳ Waiting 5s for final responses...

============================================================
📊 POST-TEST PING ANALYSIS
============================================================
📈 Response Statistics:
   Responses received: 30/30 (100.0%)
   Average response time: 2291.7ms
   Min response time: 60.5ms
   Max response time: 10658.1ms

📉 Trend Analysis:
   First half average: 4414.3ms
   Second half average: 169.2ms
   ✅ IMPROVING: Response times decreased by 96.2%
      → Cube appears to be catching up with backlog

🚦 Response Time Categories:
   Fast (<100ms): 3 (10.0%)
   Normal (100-1000ms): 16 (53.3%)
   Slow (≥1000ms): 11 (36.7%)
   ⚠️  11 slow responses indicate backlog processing

💾 Detailed results saved to: post_test_ping_results.json

🎯 RESPONSIVENESS TEST RESULTS
============================================================
Response Rate: 100.0%
Average Response: 2291.7ms
Max Response: 10658.1ms
Recovery Time: 0.8s

Grade: 🟡 FAIR
Assessment: Moderate backlog - room for improvement

📊 FINAL SUMMARY
============================================================
❌ FAIL: Cube responsiveness below acceptable thresholds
Consider MQTT performance optimizations

---

## Border Messages Non-Retained Test - stress_0.1 (Wed Aug 13 11:23:36 PDT 2025)

[2025-08-13 11:23:37] [RGBME] [INFO]: RGBME v0.12.2 - 192x256 Matrix | 1x1 Chain | 4px per LED (CIRCLE) | BrowserAdapter
[2025-08-13 11:23:37] [RGBME] [INFO]: Starting server...
[2025-08-13 11:23:37] [RGBME] [INFO]: Server started and ready to accept requests on http://localhost:8888/
pygame-ce 2.5.2 (SDL 2.30.8, Python 3.13.1)
STARTING LOGGING output/output.publish.jsonl
STARTING LOGGING None
all_cubes: {'4', '6', '3', '1', '2', '5'}, reported_cubes: set()
Player 0: Still waiting for neighbor reports from cubes: {'4', '2', '6', '3', '1', '5'}
all_cubes: {'8', '12', '11', '9', '10', '7'}, reported_cubes: set()
Player 1: Still waiting for neighbor reports from cubes: {'10', '8', '7', '12', '9', '11'}
joystick count: 0
STARTING LOGGING output/output.jsonl
all_cubes: {'4', '6', '3', '1', '2', '5'}, reported_cubes: {'4', '6', '3', '1', '2', '5'}
all cubes have neighbors
ABC start sequence activated: {'A': '1', 'B': '2', 'C': '3'}
manager.cube_chain: {'1': '2'}
manager.cube_chain: {}
manager.cube_chain: {'1': '2', '2': '3'}
starting from callback
all_cubes: {'4', '6', '3', '1', '2', '5'}, reported_cubes: {'4', '6', '3', '1', '2', '5'}
all cubes have neighbors
ABC start sequence activated: {'A': '1', 'B': '3', 'C': '4'}
898 starting new game with input_device: CubesInput
ADDED CubesInput in self.input_devices: True
start_cubes: starting letter 898
>>>>>>>> app.STARTING
initial bingo: ---------- ATTIRE --------
>>>>>>>> app.STARTED
start done
asyncio main done
🚀 CUBE RESPONSIVENESS TEST
Test: stress_0.1
Broker: 192.168.8.247
============================================================
🧪 Running functional test: stress_0.1
============================================================

✅ Test completed in 13.6s with return code: 0

⏱️  Starting responsiveness measurement in 3 seconds...

🔍 Measuring cube 1 responsiveness
============================================================
🔍 Starting post-test ping monitoring for cube 1
📊 Will ping every 2s for 90s
📡 Broker: 192.168.8.247

📤 Sent ping 1: ping_1_1755109433048
📤 Sent ping 2: ping_2_1755109435050
📤 Sent ping 3: ping_3_1755109437052
📤 Sent ping 4: ping_4_1755109439055
📤 Sent ping 5: ping_5_1755109441057
📤 Sent ping 6: ping_6_1755109443059
📤 Sent ping 7: ping_7_1755109445064
📤 Sent ping 8: ping_8_1755109447065
📤 Sent ping 9: ping_9_1755109449067
📤 Sent ping 10: ping_10_1755109451069
📤 Sent ping 11: ping_11_1755109453071
📤 Sent ping 12: ping_12_1755109455073
📤 Sent ping 13: ping_13_1755109457076
📤 Sent ping 14: ping_14_1755109459078
📤 Sent ping 15: ping_15_1755109461080
📤 Sent ping 16: ping_16_1755109463082
📤 Sent ping 17: ping_17_1755109465083
📤 Sent ping 18: ping_18_1755109467085
📤 Sent ping 19: ping_19_1755109469086
📤 Sent ping 20: ping_20_1755109471087
📤 Sent ping 21: ping_21_1755109473090
📤 Sent ping 22: ping_22_1755109475092
📤 Sent ping 23: ping_23_1755109477094
📤 Sent ping 24: ping_24_1755109479096
📤 Sent ping 25: ping_25_1755109481099
📤 Sent ping 26: ping_26_1755109483100
📤 Sent ping 27: ping_27_1755109485103
📤 Sent ping 28: ping_28_1755109487105
📤 Sent ping 29: ping_29_1755109489107
📤 Sent ping 30: ping_30_1755109491109
📤 Sent ping 31: ping_31_1755109493112
📤 Sent ping 32: ping_32_1755109495113
📤 Sent ping 33: ping_33_1755109497116
📤 Sent ping 34: ping_34_1755109499118
📤 Sent ping 35: ping_35_1755109501120
📤 Sent ping 36: ping_36_1755109503122
📤 Sent ping 37: ping_37_1755109505128
📤 Sent ping 38: ping_38_1755109507129
📤 Sent ping 39: ping_39_1755109509135
📤 Sent ping 40: ping_40_1755109511136
📥 Response: ping_1_1755109433048 -> 79644.5ms
📥 Response: ping_2_1755109435050 -> 77691.8ms
📥 Response: ping_3_1755109437052 -> 75745.5ms
📥 Response: ping_4_1755109439055 -> 73793.0ms
📥 Response: ping_5_1755109441057 -> 71837.7ms
📥 Response: ping_6_1755109443059 -> 69887.5ms
📥 Response: ping_7_1755109445064 -> 67938.6ms
📥 Response: ping_8_1755109447065 -> 65990.2ms
📥 Response: ping_9_1755109449067 -> 64038.1ms
📤 Sent ping 41: ping_41_1755109513139
📥 Response: ping_10_1755109451069 -> 62095.0ms
📥 Response: ping_11_1755109453071 -> 60136.3ms
📥 Response: ping_12_1755109455073 -> 58182.9ms
📥 Response: ping_13_1755109457076 -> 56241.8ms
📥 Response: ping_14_1755109459078 -> 54276.3ms
📥 Response: ping_15_1755109461080 -> 52542.3ms
📥 Response: ping_16_1755109463082 -> 51608.3ms
📥 Response: ping_17_1755109465083 -> 49618.1ms
📥 Response: ping_18_1755109467085 -> 47616.5ms
📥 Response: ping_19_1755109469086 -> 45616.1ms
📥 Response: ping_20_1755109471087 -> 43614.3ms
📥 Response: ping_21_1755109473090 -> 41612.1ms
📥 Response: ping_22_1755109475092 -> 39610.1ms
📥 Response: ping_23_1755109477094 -> 37608.1ms
📥 Response: ping_24_1755109479096 -> 35606.1ms
📥 Response: ping_25_1755109481099 -> 33603.4ms
📥 Response: ping_26_1755109483100 -> 31601.7ms
📥 Response: ping_27_1755109485103 -> 29599.1ms
📥 Response: ping_28_1755109487105 -> 27597.0ms
📥 Response: ping_29_1755109489107 -> 25595.2ms
📥 Response: ping_30_1755109491109 -> 23593.0ms
📥 Response: ping_31_1755109493112 -> 21590.8ms
📥 Response: ping_32_1755109495113 -> 19589.2ms
📥 Response: ping_33_1755109497116 -> 17587.0ms
📥 Response: ping_34_1755109499118 -> 15588.4ms
📥 Response: ping_35_1755109501120 -> 13586.7ms
📥 Response: ping_36_1755109503122 -> 11584.9ms
📥 Response: ping_37_1755109505128 -> 9579.4ms
📥 Response: ping_38_1755109507129 -> 7578.0ms
📥 Response: ping_39_1755109509135 -> 5572.9ms
📥 Response: ping_40_1755109511136 -> 3571.2ms
📥 Response: ping_41_1755109513139 -> 1569.2ms
📤 Sent ping 42: ping_42_1755109515140
📥 Response: ping_42_1755109515140 -> 56.4ms
📤 Sent ping 43: ping_43_1755109517141
📥 Response: ping_43_1755109517141 -> 80.6ms
📤 Sent ping 44: ping_44_1755109519143
📥 Response: ping_44_1755109519143 -> 126.8ms
📤 Sent ping 45: ping_45_1755109521146
📥 Response: ping_45_1755109521146 -> 185.0ms

⏳ Waiting 5s for final responses...

============================================================
📊 POST-TEST PING ANALYSIS
============================================================
📈 Response Statistics:
   Responses received: 45/45 (100.0%)
   Average response time: 37377.5ms
   Min response time: 56.4ms
   Max response time: 79644.5ms

📉 Trend Analysis:
   First half average: 59515.3ms
   Second half average: 16202.2ms
   ✅ IMPROVING: Response times decreased by 72.8%
      → Cube appears to be catching up with backlog

🚦 Response Time Categories:
   Fast (<100ms): 2 (4.4%)
   Normal (100-1000ms): 2 (4.4%)
   Slow (≥1000ms): 41 (91.1%)
   ⚠️  41 slow responses indicate backlog processing

💾 Detailed results saved to: post_test_ping_results.json

🎯 RESPONSIVENESS TEST RESULTS
============================================================
Response Rate: 100.0%
Average Response: 37377.5ms
Max Response: 79644.5ms
Recovery Time: 2.5s

Grade: 🔴 POOR
Assessment: High latency indicates significant message backlog

📊 FINAL SUMMARY
============================================================
❌ FAIL: Cube responsiveness below acceptable thresholds
Consider MQTT performance optimizations
