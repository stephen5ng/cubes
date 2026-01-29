#!/usr/bin/env python3
"""Interactive test program to visualize the stars and tada blink animation."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import pygame
from game.components import StarsDisplay
from config import game_config


class MockRackMetrics:
    LETTER_SIZE = 40


class MockSoundManager:
    def play_starspin(self):
        print("🔊 Sound: Starspin")

    def play_tada(self):
        print("🎉 Sound: Tada!")

    def get_starspin_length(self):
        return 0.5  # 0.5 seconds


def main():
    pygame.init()

    real_width = game_config.SCREEN_WIDTH
    real_height = 120
    factor = game_config.SCALING_FACTOR

    # Create the real window with scaled dimensions
    window = pygame.display.set_mode((real_width * factor, real_height * factor))
    # Create a small surface for low-res rendering
    screen = pygame.Surface((real_width, real_height))

    pygame.display.set_caption("Stars Animation Test - Press SPACE to earn stars, R to reset, ESC to quit")
    clock = pygame.time.Clock()

    # Setup
    metrics = MockRackMetrics()
    stars = StarsDisplay(metrics, min_win_score=30, sound_manager=MockSoundManager())

    # Position stars in center
    total_width = stars.surface.get_width()
    stars.pos = [real_width // 2 - total_width // 2, real_height // 2 - stars.surface.get_height() // 2]

    running = True
    frame_count = 0
    last_printed_ms = -1

    print("\n" + "=" * 60)
    print("STARS ANIMATION TEST")
    print("=" * 60)
    print("\nControls:")
    print("  SPACE: Earn 1 more star (0→1→2→3)")
    print("  R:     Reset to 0 stars")
    print("  ESC:   Quit")
    print("\nAnimation Sequence:")
    print("  1. Earn stars 1 & 2: each spins in individually")
    print("  2. Earn star 3: spins in, then ALL 3 STARS blink (tada!)")
    print("\nPress SPACE to start earning stars...\n")

    current_score = 0
    stars_earned = 0

    while running:
        now_ms = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    # Earn next star progressively
                    if stars_earned < 3:
                        stars_earned += 1
                        current_score = stars_earned * 10
                        stars.draw(current_score, now_ms)

                        if stars_earned < 3:
                            print(f"⭐ Star {stars_earned} earned! (spinning in...)")
                        else:
                            print(f"⭐⭐⭐ STAR 3 EARNED! (spinning in... then TADA!)")
                    else:
                        print("  (Already have 3 stars! Press R to reset)")
                elif event.key == pygame.K_r:
                    current_score = 0
                    stars_earned = 0
                    stars.draw(0, now_ms)
                    stars._last_filled_count = 0
                    stars._tada_scheduled_ms = -1
                    stars._heartbeat_start_ms = -1
                    stars._render_surface(now_ms)
                    print("🔄 Reset to 0 stars")

        # Debug output during tada animation
        if stars._heartbeat_start_ms > 0:
            elapsed = now_ms - stars._heartbeat_start_ms
            if elapsed - last_printed_ms >= 150:
                opacity = stars._get_blink_opacity(elapsed)
                if elapsed < 200:
                    phase = "Blink 1"
                elif elapsed < 400:
                    phase = "Blink 2"
                elif elapsed < 600:
                    phase = "Blink 3"
                else:
                    phase = "Resting"

                blink_state = "💫" if opacity < 0.7 else "✨"
                print(f"  [{elapsed:4d}ms] {phase:10s} {blink_state} (opacity: {opacity:.2f})")
                last_printed_ms = elapsed

        # Draw to low-res screen
        screen.fill((20, 20, 40))  # Dark blue background

        # Draw some UI text
        font = pygame.freetype.SysFont("Arial", 14)
        score_text = f"Score: {current_score}/30"
        font.render_to(screen, (5, 5), score_text, (200, 200, 200))

        stars.update(screen, now_ms)

        # Scale up to window
        scaled = pygame.transform.scale(screen, window.get_size())
        window.blit(scaled, (0, 0))

        pygame.display.flip()
        frame_count += 1
        clock.tick(60)

    pygame.quit()
    print("\n✋ Goodbye!\n")


if __name__ == "__main__":
    main()
