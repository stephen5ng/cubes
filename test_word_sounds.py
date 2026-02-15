#!/usr/bin/env python3
"""Test script to verify word sounds work."""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, 'src')

from systems.sound_manager import SoundManager

async def test_word_sounds():
    print("Testing word sounds...")

    # Check if sound files exist
    test_words = ["sot", "sort", "pal", "cat", "dog"]
    for word in test_words:
        for player in [1, 2]:
            soundfile = f"assets/word_sounds_{player}/{word.lower()}.wav"
            if os.path.exists(soundfile):
                print(f"✓ {soundfile} exists")
            else:
                print(f"✗ {soundfile} NOT FOUND")

    # Initialize pygame and sound manager
    try:
        import pygame
        pygame.init()
        pygame.mixer.init()
        sound_manager = SoundManager()
        print("Sound manager initialized successfully")
    except Exception as e:
        print(f"Failed to initialize sound manager: {e}")
        return

    # Test queuing word sounds
    print("\nTesting word sound queuing...")
    test_words = ["sot", "sort", "pal"]
    for word in test_words:
        print(f"Queueing '{word}'...")
        await sound_manager.queue_word_sound(word, 1)

    # Give some time for sounds to play
    print("\nWaiting for sounds to play...")
    await asyncio.sleep(5)

    print("Test complete!")

if __name__ == "__main__":
    asyncio.run(test_word_sounds())