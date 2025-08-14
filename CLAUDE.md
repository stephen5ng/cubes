# BlockWords Cubes Project Memory

## Current Focus: Latency Metrics Logging Implementation

### Problem Context
- **Physical cube display latency**: ESP32 displays on physical cubes are slow to update
- Discord discussions identified latency issues during gameplay
- MQTT roundtrip delays affecting cube responsiveness between game server and ESP32s
- Need "end to end latency analyzer for ESP32 mqtt wifi"
- Event system analysis recommends monitoring event processing latency
- Existing logging system uses JSONL format for game replay
- **Holistic solution needed**: Must address latency across entire pipeline from game → MQTT → ESP32 → display

### Approved Implementation Plan: Separate Latency Logger

**Approach**: Create dedicated `LatencyLogger` class parallel to existing `GameLogger`

**Benefits**:
- Clean separation of concerns
- Won't interfere with existing replay system  
- Easy to enable/disable independently
- Optimized for performance analysis

**Key Components**:
- Separate log file: `latency_metrics.jsonl`
- High-precision timestamps (`time.perf_counter()`)
- Minimal overhead measurement points
- Configurable sampling rates

**Critical Measurement Points** (End-to-End Pipeline):
1. **Game server event processing**: trigger → MQTT publish
2. **MQTT network latency**: publish → ESP32 receive  
3. **ESP32 MQTT receive → display update start** (main.cpp letter handler)
4. **ESP32 animation processing** (main.cpp, currently 1000ms `ANIMATION_DURATION_MS`)
5. **ESP32 DMA buffer operations** (main.cpp:460 flipDMABuffer)
6. **Full roundtrip**: game state change → visible cube display
7. **Input device response**: hardware input → game state change

### Implementation Status
- [x] Analyzed existing logging system integration points
- [x] Designed latency metrics collection strategy  
- [x] Planned implementation approach
- [x] Analyzed ESP32 cube firmware architecture and pipeline
- [x] Identified ESP32 latency bottlenecks and measurement points
- [ ] Implement LatencyLogger class (Python game server)
- [ ] Add ESP32 firmware latency instrumentation 
- [ ] Add MQTT timing instrumentation (bidirectional)
- [ ] Add event processing timing
- [ ] Add input device timing
- [ ] Add rendering pipeline timing
- [ ] Create configuration system
- [ ] Add tests and validation

### Key Files
**Game Server (Python)**:
- `main.py`: Contains existing `GameLogger` class
- `pygamegameasync.py`: Main game loop and MQTT handling
- `LOGGING_README.md`: Documents current logging system
- `tests/test_logging.py`: Logging test patterns

**ESP32 Cube Firmware**:
- `/Users/stephenng/Documents/PlatformIO/Projects/cube-pn5180/`: ESP32 source code
- Physical cube displays and MQTT client implementation
- `src/main.cpp`: Main firmware with DisplayManager class and MQTT handlers
- `src/cube_utilities.h/.cpp`: MAC address mapping and MQTT topic utilities

### ESP32 Architecture Analysis

**Hardware Components**:
- ESP32 with 64x64 HUB75 LED matrix display (DMA-accelerated)
- PN5180 NFC reader for cube-to-cube communication
- WiFi + MQTT client for game server communication
- UDP ping/pong diagnostics (port 54321)

**MQTT → Display Pipeline** (main.cpp):
1. **MQTT Message Receive** (line 710 - subscription handlers)
2. **Command Processing** (DisplayManager class methods)
3. **Animation State Update** (`animate()` method at line 293)
4. **Display Buffer Update** (`updateDisplay()` at line 429)  
5. **DMA Buffer Flip** (`flipDMABuffer()` at line 460)

**Identified Latency Bottlenecks**:
- **Animation duration** (`ANIMATION_DURATION_MS`) — currently 1000ms; previously tested at 200ms and 800ms
- **MQTT receive → display pipeline** not fully instrumented
- **DMA buffer operations** potentially blocking
- **Message gap detection** already exists (>1s warnings at line 541)

**Existing Timing Infrastructure**:
- MQTT publish timing (lines 871-874)
- Message gap detection (lines 541-545)  
- UDP ping/pong for network diagnostics
- Each cube has dual MAC addresses (main + front display)

### Integration Points
- **Python GameLogger** class in main.py:64
- **Python MQTT handling** in pygamegameasync.py
- **ESP32 DisplayManager** class in main.cpp:204
- **ESP32 MQTT handlers** in main.cpp:685-716
- **ESP32 animation system** in main.cpp:293-323
- Event system in pygameasync.py  
- Input devices in src/input/input_devices.py

**Coding guidelines**
- In general, don't use default parameters. It's better to force the client to explicitly specify parameters.
- Don't document lines of code that are obvious (per Google style guidelines)
- There is a python virtual environment in ./cube_env.
- Python imports should generally be at the top of the file.

### Build, Deploy, and Test Procedures

Assumptions
- Game repo: `/Users/stephenng/programming/blockwords/cubes`
- ESP32 firmware repo: `/Users/stephenng/Documents/PlatformIO/Projects/cube-pn5180`
- Cube 1 IP: `192.168.8.21`
- Virtualenvs: cubes has `./cube_env`; firmware has `./venv`

#### Build ESP32 firmware
```bash
/Users/stephenng/Documents/PlatformIO/Projects/cube-pn5180/venv/bin/pio run -e esp32dev
```
- Output: `/Users/stephenng/Documents/PlatformIO/Projects/cube-pn5180/.pio/build/esp32dev/firmware.bin`

#### OTA deploy to cube 1
```bash
python3 ~/.platformio/packages/framework-arduinoespressif32/tools/espota.py \
  -i 192.168.8.21 -d -r \
  -f "/Users/stephenng/Documents/PlatformIO/Projects/cube-pn5180/.pio/build/esp32dev/firmware.bin"
```

#### Quick responsiveness test (SNG)
From the game repo:
```bash
./test_cube_responsiveness.py sng
```
- Uses broker `192.168.8.247`, writes `post_test_ping_results.json` and prints summary

#### Medium stress responsiveness test (stress_0.1)
```bash
./test_cube_responsiveness.py stress_0.1
```

#### Direct ping/echo latency probe (no replay)
```bash
./cube_env/bin/python post_test_ping_monitor.py \
  --broker 192.168.8.247 \
  --cube-id 1 \
  --duration 10 \
  --interval 1
```

Troubleshooting
- If `pio` not found in cubes venv, use firmware venv path:
```bash
/Users/stephenng/Documents/PlatformIO/Projects/cube-pn5180/venv/bin/pio --version
```
- If OTA upload fails, retry once:
```bash
python3 ~/.platformio/packages/framework-arduinoespressif32/tools/espota.py -i 192.168.8.21 -d -r -f "/Users/stephenng/Documents/PlatformIO/Projects/cube-pn5180/.pio/build/esp32dev/firmware.bin"
```