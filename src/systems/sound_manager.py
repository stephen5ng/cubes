"""Sound management system for the Blockwords game."""

import asyncio
from datetime import datetime
import pygame


class SoundManager:
    """Manages sound effects and word pronunciation for the game."""
    
    DELAY_BETWEEN_WORD_SOUNDS_S = 0.3

    def __init__(self):
        self.sound_queue: asyncio.Queue = asyncio.Queue()
        self.start_sound = pygame.mixer.Sound("assets/sounds/start.wav")
        self.crash_sound = pygame.mixer.Sound("assets/sounds/ping.wav")
        self.crash_sound.set_volume(0.8)
        self.chunk_sound = pygame.mixer.Sound("assets/sounds/chunk.wav")
        self.game_over_sound = pygame.mixer.Sound("assets/sounds/game_over.wav")
        self.bloop_sound = pygame.mixer.Sound("assets/sounds/bloop.wav")
        self.bloop_sound.set_volume(0.2)
        
        self.letter_beeps: list = []
        for n in range(11):
            self.letter_beeps.append(pygame.mixer.Sound(f"assets/sounds/{n}.wav"))
            
        # UI sounds
        self.add_sound = pygame.mixer.Sound("assets/sounds/add.wav")
        self.erase_sound = pygame.mixer.Sound("assets/sounds/erase.wav")
        self.cleared_sound = pygame.mixer.Sound("assets/sounds/cleared.wav")
        self.left_sound = pygame.mixer.Sound("assets/sounds/left.wav")
        self.right_sound = pygame.mixer.Sound("assets/sounds/right.wav")
        self.tada_sound = pygame.mixer.Sound("assets/sounds/tada.wav")
        self.starspin_sound = pygame.mixer.Sound("assets/sounds/starspin.wav")
        self.sad_trombone_sound = pygame.mixer.Sound("assets/sounds/sad_trombone.wav")
        
        self.left_sound.set_volume(0.5)
        self.right_sound.set_volume(0.5)
        self.tada_sound.set_volume(0.8)
        self.starspin_sound.set_volume(1.0)

        self.sound_queue_task = asyncio.create_task(self.play_sounds_in_queue(), name="word sound player")

    def get_letter_beeps(self) -> list:
        """Get the letter beeps list for use by other components."""
        return self.letter_beeps

    async def play_sounds_in_queue(self) -> None:
        """Background task to play word sounds with proper timing."""
        pygame.mixer.set_reserved(2)
        delay_between_words_s = self.DELAY_BETWEEN_WORD_SOUNDS_S
        last_sound_time = datetime(year=1, month=1, day=1)
        while True:
            try:
                soundfile = await self.sound_queue.get()
                # Prepend 'assets/' if it's a word sound
                if soundfile.startswith('word_sounds_'):
                    soundfile = f"assets/{soundfile}"
                s = pygame.mixer.Sound(soundfile)
                now = datetime.now()
                time_since_last_sound_s = (now - last_sound_time).total_seconds()
                time_to_sleep_s = delay_between_words_s - time_since_last_sound_s
                await asyncio.sleep(time_to_sleep_s)
                channel = pygame.mixer.find_channel(force=True)
                channel.queue(s)
                last_sound_time = datetime.now()
            except Exception as e:
                print(f"error playing sound {soundfile}: {e}")
                continue

    async def queue_word_sound(self, word: str, player: int) -> None:
        """Queue a word pronunciation sound for playback."""
        soundfile = f"word_sounds_{player}/{word.lower()}.wav"
        print(f"[DEBUG] Attempting to queue word sound: {soundfile}")
        print(f"[DEBUG] Word exists: {os.path.exists(soundfile)}")
        await self.sound_queue.put(soundfile)

    def play_start(self) -> None:
        """Play game start sound."""
        pygame.mixer.Sound.play(self.start_sound)

    def play_crash(self) -> None:
        """Play crash/collision sound."""
        pygame.mixer.Sound.play(self.crash_sound)

    def play_chunk(self) -> None:
        """Play chunk/drop sound."""
        pygame.mixer.Sound.play(self.chunk_sound)

    def play_game_over(self) -> None:
        """Play game over sound."""
        pygame.mixer.Sound.play(self.game_over_sound)

    def play_bloop(self) -> None:
        """Play bloop sound."""
        pygame.mixer.Sound.play(self.bloop_sound)

    def play_add(self) -> None:
        """Play letter add sound."""
        pygame.mixer.Sound.play(self.add_sound)

    def play_erase(self) -> None:
        """Play letter erase sound."""
        pygame.mixer.Sound.play(self.erase_sound)

    def play_cleared(self) -> None:
        """Play rack cleared sound."""
        pygame.mixer.Sound.play(self.cleared_sound)

    def play_left(self) -> None:
        """Play cursor move left sound."""
        pygame.mixer.Sound.play(self.left_sound)

    def play_right(self) -> None:
        """Play cursor move right sound."""
        pygame.mixer.Sound.play(self.right_sound)

    def play_tada(self) -> None:
        """Play tada/victory fanfare sound."""
        pygame.mixer.Sound.play(self.tada_sound)

    def play_starspin(self) -> None:
        """Play star earned sound."""
        pygame.mixer.Sound.play(self.starspin_sound)

    def get_starspin_length(self) -> float:
        """Get the length of the starspin sound in seconds."""
        return self.starspin_sound.get_length()

    def play_sad_trombone(self) -> None:
        """Play sad trombone sound."""
        pygame.mixer.Sound.play(self.sad_trombone_sound)