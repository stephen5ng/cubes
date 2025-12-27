# BlockWords Cubes

A physical word game that combines Scrabble-like gameplay with interactive ESP32-based cubes featuring LED matrix displays. Players form words from letters displayed on physical cubes, with real-time communication via MQTT.

## Overview

BlockWords Cubes is a multiplayer word game where:
- 6 physical cubes per player display letters on RGB LED matrices
- Players form words from available letters to score points
- A falling letter mechanic adds time pressure
- Cubes communicate via MQTT protocol for multiplayer coordination
- Game supports 1-2 players with independent or synchronized starts

## Hardware Requirements

### Physical Cubes
- **ESP32 microcontrollers** - One per cube (12 total for 2 players)
- **64x64 RGB LED matrices (HUB75)** - For letter display
- **MQTT broker** - For cube-to-game communication
- **Cube IDs:**
  - Player 0 (P0): Cubes 1-6
  - Player 1 (P1): Cubes 11-16

### Development Machine
- macOS, Linux, or Windows
- Python 3.9+
- MQTT broker (Mosquitto recommended)

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/stephen5ng/cubes.git
cd cubes
```

### 2. Set Up Python Environment
```bash
python3 -m venv cube_env
source cube_env/bin/activate  # On Windows: cube_env\Scripts\activate
pip install -r requirements.txt
```

### 3. Install MQTT Broker (if not already installed)
```bash
# macOS
brew install mosquitto
brew services start mosquitto

# Linux
sudo apt-get install mosquitto mosquitto-clients
sudo systemctl start mosquitto
```

### 4. Set Environment Variables
```bash
export MQTT_SERVER=localhost  # Or your MQTT broker IP
export PYTHONPATH=../easing-functions:../rpi-rgb-led-matrix/bindings/python:$PYTHONPATH
```

## Running the Game

### Start the Game Server
```bash
./runpygame.sh
```

### Start with Keyboard Controls
Press `ESC` to start a game. Use keyboard to form words:
- **Arrow keys**: Navigate letters
- **Letter keys**: Add letters to current word
- **SPACE**: Toggle letter selection
- **BACKSPACE**: Remove last letter
- **RETURN**: Clear current word
- **TAB**: Toggle 1-player/2-player mode

### Start with Physical Cubes (ABC Sequence)
Players arrange their cubes in A-B-C sequence by placing cubes next to each other:
1. Place cube showing 'A'
2. Place cube showing 'B' next to the 'A' cube (right side touches)
3. Place cube showing 'C' next to the 'B' cube
4. Game starts automatically after countdown

For 2-player mode, both players can complete ABC sequence to join the same game.

## Testing

### Run Unit Tests
```bash
./run_unit_tests.sh
```

### Run Functional Tests
Functional tests use replay files to ensure consistent behavior:
```bash
./run_functional_tests.sh
```

### Run Individual Functional Test
```bash
./functional_test.py replay <test_name>
# Example:
./functional_test.py replay 2player
```

### Record New Golden Files
```bash
./functional_test.py record <test_name>
```

### Update Existing Golden Files
```bash
./functional_test.py rerecord <test_name>
```

## Project Structure

```
cubes/
├── src/                          # Organized source code
│   └── blockwords/
│       ├── core/                 # Core game logic (in progress)
│       ├── game/                 # Game components
│       ├── input/                # Input device handlers
│       ├── rendering/            # Display and animations
│       ├── systems/              # Sound, events
│       └── ui/                   # UI components
│
├── tests/                        # Test suite
│   ├── e2e/                     # End-to-end tests
│   ├── integration/             # Integration tests
│   └── *.py                     # Unit tests
│
├── scripts/                      # Utility scripts
│   ├── monitoring/              # Cube monitoring tools
│   ├── analysis/                # Performance analysis
│   └── utilities/               # Test utilities
│
├── tools/                        # Development tools
│   └── *.sh                     # Shell utilities
│
├── replay/                       # Replay files for tests
├── goldens/                      # Golden output files
├── sounds/                       # Audio assets
├── data/                         # Dictionary files
│
├── app.py                        # Main application logic
├── main.py                       # Entry point
├── cubes_to_game.py             # MQTT cube communication
├── pygamegameasync.py           # Game loop and rendering
├── tiles.py                      # Tile/letter management
├── dictionary.py                 # Word validation
├── scorecard.py                  # Scoring logic
│
├── run_unit_tests.sh            # Test runner
├── run_functional_tests.sh      # Functional test runner
└── runpygame.sh                 # Game launcher
```

## Architecture

### Key Components

**Game Server (main.py, pygamegameasync.py)**
- Pygame-based rendering
- Event-driven architecture using custom async event engine
- Handles input from keyboard, gamepad, or physical cubes
- 45 FPS game loop with async MQTT processing

**Cube Communication (cubes_to_game.py)**
- MQTT-based protocol for cube neighbor detection
- ABC countdown sequence management
- Per-player game state tracking
- Topics: `cube/right/{sender}` with numeric cube IDs

**Game Logic (app.py, tiles.py, scorecard.py)**
- Letter frequency distribution (English or Scrabble)
- Word validation against SOWPODS dictionary
- Scoring: word length + 10 point bonus for 6-letter words
- Rack management with letter replacement

**Rendering (pygamegameasync.py, src/rendering/)**
- 192x256 pixel display (scaled 3x for development)
- Falling letter animation with physics
- Fading word displays
- Per-player score and shield animations

### MQTT Protocol

**Neighbor Detection:**
```
Topic: cube/right/{sender_cube_id}
Payload: "{neighbor_cube_id}" or "" (to clear)
```

**Game Control:**
```
Topic: app/start    - Start game
Topic: app/abort    - Abort game
Topic: game/guess   - Submit word guess
```

## Development Workflow

### Before Committing
1. Run unit tests: `./run_unit_tests.sh`
2. Consider functional tests for critical changes
3. Check CLAUDE.md for project-specific guidelines

### Adding New Features
1. Write unit tests first
2. Implement feature
3. Update functional tests if needed
4. Update golden files: `./functional_test.py rerecord <test>`

### Monitoring Cubes
```bash
# Monitor cube latency
python scripts/monitoring/cube_latency_monitor.py

# Monitor all cubes
python scripts/monitoring/monitor_cubes.py

# Dashboard
python scripts/monitoring/dashboard.py
```

## Configuration

Key configuration values in `config.py`:
- `MAX_PLAYERS = 2` - Maximum number of players
- `MQTT_CLIENT_PORT = 1883` - MQTT broker port

Cube ID ranges:
- Player 0: 1-6
- Player 1: 11-16

## Troubleshooting

### MQTT Connection Issues
```bash
# Check if MQTT broker is running
nc -zv localhost 1883

# Start mosquitto manually
mosquitto -c /opt/homebrew/etc/mosquitto/mosquitto.conf
```

### Game Won't Start
- Check virtual environment is activated
- Verify PYTHONPATH includes required dependencies
- Check cube neighbor connections (for physical cubes)

### Tests Failing
- Ensure MQTT_SERVER=localhost for tests
- Clean output directory: `rm -rf output/`
- Check replay files exist in `replay/` directory

## Contributing

### Code Style
- Follow existing patterns
- Add type hints to new functions
- Keep functions focused and small
- Write tests for new features

### Testing Requirements
- Unit tests for all new logic
- Functional replay tests for user-facing changes
- Examine updated golden files to ensure they make sense

## License

[Add license information]

## Credits

Built by Stephen Ng

Uses:
- Pygame for rendering
- MQTT for cube communication
- HUB75 LED matrices for display
- SOWPODS dictionary for word validation
