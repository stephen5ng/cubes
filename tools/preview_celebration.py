import asyncio
import pygame
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.app import App
from core.dictionary import Dictionary
from hardware.interface import HardwareInterface
from game.game_coordinator import GameCoordinator
from rendering.metrics import RackMetrics
from config.game_config import SCREEN_WIDTH, SCREEN_HEIGHT, SCALING_FACTOR, TICKS_PER_SECOND
from utils import hub75

class MockHardware(HardwareInterface):
    def set_guess_tiles_callback(self, callback): pass
    def set_start_game_callback(self, callback): pass
    def get_started_cube_sets(self): return [0]
    def reset_player_started_state(self): pass
    def add_player_started(self, player_id): pass
    def set_game_running(self, running): pass
    def has_player_started_game(self, player_id): return player_id == 0
    async def clear_remaining_abc_cubes(self, q, now): pass
    async def guess_last_tiles(self, q, cid, p, now): pass
    async def load_rack(self, q, tiles, cid, p, now): pass
    def set_game_end_time(self, now): pass
    async def unlock_all_letters(self, q, now): pass
    async def clear_all_letters(self, q, now): pass
    async def clear_all_borders(self, q, now): pass
    async def accept_new_letter(self, q, letter, tid, cid, now): pass
    async def letter_lock(self, q, cid, tid, now): return False
    async def old_guess(self, q, ids, cid, p): pass
    async def good_guess(self, q, ids, cid, p, now): pass
    async def bad_guess(self, q, ids, cid, p): pass
    async def guess_tiles(self, q, ids, cid, p, now): pass
    def remove_player_from_abc_tracking(self, pid): pass

async def preview():
    pygame.init()
    window = pygame.display.set_mode((SCREEN_WIDTH * SCALING_FACTOR, SCREEN_HEIGHT * SCALING_FACTOR))
    pygame.display.set_caption("Celebration Preview")

    # Mock dependencies
    class MockLogger:
        def log_events(self, *args, **kwargs): pass
        def stop_logging(self, *args, **kwargs): pass
        def start_logging(self, *args, **kwargs): pass

    # Setup core dependencies
    publish_queue = asyncio.Queue()
    dictionary = Dictionary.from_words(["HELLO", "WORLD", "WINNER", "TEST"])
    hardware = MockHardware()

    app = App(publish_queue, dictionary, hardware)

    # Setup game components
    # We need a font for the letters
    letter_font = pygame.freetype.SysFont("Arial", RackMetrics.LETTER_SIZE)

    # Initialize game through coordinator to ensure all systems are connected
    from systems.sound_manager import SoundManager
    from game.game_state import Game
    from game.descent_strategy import DescentStrategy
    from game.recorder import NullRecorder

    sound_manager = SoundManager()
    rack_metrics = RackMetrics()
    descent_strategy = DescentStrategy(game_duration_ms=1000, event_descent_amount=0)

    game = Game(
        app, letter_font, MockLogger(), MockLogger(), sound_manager,
        rack_metrics, sound_manager.get_letter_beeps(),
        letter_strategy=descent_strategy, recovery_strategy=descent_strategy,
        descent_duration_s=10, recorder=NullRecorder(),
        replay_mode=False, one_round=True, min_win_score=30, stars=True, level=1
    )

    # Prepare the "Win" state
    now_ms = pygame.time.get_ticks()
    # We need to set the app in the game
    game._app = app

    # Start game
    await game.start_cubes(now_ms)

    # 1. Earn 3 stars
    game.scores[0].score = 30
    game.stars_display.draw(game.scores[0].score, now_ms)

    # 2. Add some guesses for balloons
    game.guesses_manager.add_guess(["HELLO", "WORLD", "WINNER"], "WINNER", 0, now_ms)

    # 3. Trigger Win
    await game.stop(now_ms, exit_code=10)

    print("Previewing Celebration Phase...")
    print("Press ESC or close window to exit.")

    clock = pygame.time.Clock()
    running = True
    while running:
        now_ms = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        screen.fill((0, 0, 0))

        # Update and draw
        await game.update(screen, now_ms)

        # Scale to window
        pygame.transform.scale(screen, window.get_rect().size, dest_surface=window)
        pygame.display.flip()

        await asyncio.sleep(1/TICKS_PER_SECOND)

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(preview())
