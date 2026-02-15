#!/usr/bin/env python3
"""Simple sound test."""

import pygame
import os

pygame.init()
pygame.mixer.init()

print("Testing sound file loading...")

# Test loading a word sound directly
try:
    sound = pygame.mixer.Sound('assets/word_sounds_1/sot.wav')
    print(f"✓ sot.wav loaded: {sound.get_length():.2f}s")
    sound.play()
    import time
    time.sleep(1)
except Exception as e:
    print(f"✗ Error loading sot.wav: {e}")

# Test with full path
try:
    sound = pygame.mixer.Sound('/opt/lexacube/assets/word_sounds_1/sot.wav')
    print(f"✓ Full path works: {sound.get_length():.2f}s")
    sound.play()
    time.sleep(1)
except Exception as e:
    print(f"✗ Full path failed: {e}")

print("Test complete")