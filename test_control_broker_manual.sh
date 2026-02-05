#!/bin/bash
# Manual test for control broker final score display
#
# Prerequisites: Start a control broker manually:
#   mosquitto -p 1884 -v
#
# Or let runpygame.sh start it for you.

set -e

mqtt_control_port=${MQTT_CONTROL_PORT:-1884}

echo "Testing Control Broker Final Score Display"
echo "==========================================="
echo ""

# Check if broker is running
if ! nc -zv localhost $mqtt_control_port > /dev/null 2>&1; then
    echo "❌ Control broker not running on port $mqtt_control_port"
    echo ""
    echo "Please start it manually:"
    echo "  mosquitto -p $mqtt_control_port"
    echo ""
    echo "Or run: ./runpygame.sh (it will start both brokers automatically)"
    exit 1
fi

echo "✓ Control broker is running on port $mqtt_control_port"
echo ""

# Publish a test final score message
echo "Publishing test final score message..."
test_score='{
  "score": 150,
  "stars": 5,
  "exit_code": 10,
  "min_win_score": 90,
  "duration_s": 123.4
}'

mosquitto_pub -h localhost -p $mqtt_control_port -t "game/final_score" -m "$test_score"
echo "✓ Test message published"
echo ""

# Fetch and display using the function from runpygame.sh
echo "Fetching final score from broker..."
score_json=$(timeout 2 mosquitto_sub -h localhost -p $mqtt_control_port -t "game/final_score" -C 1 2>/dev/null)

if [ -n "$score_json" ]; then
    echo ""
    echo "=========================================="
    echo "           FINAL SCORE"
    echo "=========================================="

    python3 -c "
import json
try:
    data = json.loads('''$score_json''')
    print(f\"  Score:        {data.get('score', 'N/A')}\")
    print(f\"  Stars:        {data.get('stars', 'N/A')}\")
    exit_code = data.get('exit_code', 'N/A')
    result = 'Win' if exit_code == 10 else ('Loss' if exit_code == 11 else 'Quit/Abort')
    print(f\"  Result:       {result} (exit code: {exit_code})\")
    print(f\"  Duration:     {data.get('duration_s', 0):.1f}s\")
    if data.get('min_win_score', 0) > 0:
        print(f\"  Win Target:   {data.get('min_win_score', 0)}\")
except Exception as e:
    print(f\"Error: {e}\")
    import sys
    sys.exit(1)
"
    echo "=========================================="
    echo ""
    echo "✅ Test PASSED! Final score successfully fetched and displayed."
    echo ""
    echo "Now try running a real game:"
    echo "  ./runpygame.sh --mode game_on --level 0"
    echo ""
    echo "The final score will be displayed automatically after the game ends."
else
    echo "❌ Test FAILED: No final score message received"
    exit 1
fi
