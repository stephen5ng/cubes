"""Sound management system for the Blockwords game."""

import asyncio
from datetime import datetime
import aiofiles
import pygame


class SoundManager:
    """Manages sound effects and word pronunciation for the game."""
    
    DELAY_BETWEEN_WORD_SOUNDS_S = 0.3

    def __init__(self):
        self.sound_queue: asyncio.Queue = asyncio.Queue()
        self.start_sound = pygame.mixer.Sound("./sounds/start.wav")
        self.crash_sound = pygame.mixer.Sound("./sounds/ping.wav")
        self.crash_sound.set_volume(0.8)
        self.chunk_sound = pygame.mixer.Sound("./sounds/chunk.wav")
        self.game_over_sound = pygame.mixer.Sound("./sounds/game_over.wav")
        self.bloop_sound = pygame.mixer.Sound("./sounds/bloop.wav")
        self.bloop_sound.set_volume(0.2)
        
        # Initialize letter beeps - these are used by the Letter class
        self.letter_beeps: list = []
        for n in range(11):
            self.letter_beeps.append(pygame.mixer.Sound(f"sounds/{n}.wav"))
            
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
                async with aiofiles.open(soundfile, mode='rb') as f:
                    s = pygame.mixer.Sound(buffer=await f.read())
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
        await self.sound_queue.put(f"word_sounds_{player}/{word.lower()}.wav")

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