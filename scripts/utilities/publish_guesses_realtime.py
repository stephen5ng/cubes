#!/usr/bin/env python3

import os
import sys
import paho.mqtt.client as mqtt
import termios
import tty

def get_char():
    """Get a single character from stdin without requiring Enter."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def update_word(client, word):
    """Update the current word, publish it, and refresh display."""
    client.publish("game/guess", word)
    print('\r' + ' ' * (len(word) + 20) + '\rCurrent word: ' + word, end="", flush=True)

def main():
    if not (mqtt_server := os.environ.get('MQTT_SERVER')):
        print("Error: MQTT_SERVER environment variable is not set")
        print("Please set it first with: export MQTT_SERVER=your_mqtt_server")
        sys.exit(1)

    client = mqtt.Client()
    client.connect(mqtt_server)
    client.loop_start()

    current_word = ""
    print("Type letters to form a word (Backspace to delete, Enter to clear, Ctrl+C to exit):")
    print("Current word:", end=" ", flush=True)

    try:
        while True:
            char = get_char()
            if char == '\x03':  # Ctrl+C
                break
            elif char == '\x7f':  # Backspace
                if current_word:
                    current_word = current_word[:-1]
                    update_word(client, current_word)
            elif char == '\r':  # Enter
                current_word = ""
                update_word(client, current_word)
            elif char.isalpha():
                current_word += char.upper()
                update_word(client, current_word)

    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main() 