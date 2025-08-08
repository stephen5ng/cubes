"""Mock SoundManager for testing - demonstrates DI benefits."""

import asyncio
from typing import List


class MockSoundManager:
    """Mock sound manager that doesn't actually play sounds - perfect for testing."""
    
    def __init__(self):
        self.sound_queue: asyncio.Queue = asyncio.Queue()
        self.letter_beeps: List = [f"mock_beep_{i}" for i in range(11)]  # Mock letter beeps
        self.played_sounds = []  # Track what sounds were "played" for testing
        self.sound_queue_task = None  # Don't start real async task in tests

    def get_letter_beeps(self) -> List:
        """Get mock letter beeps for testing."""
        return self.letter_beeps

    async def play_sounds_in_queue(self) -> None:
        """Mock implementation - just records sounds instead of playing."""
        while True:
            try:
                soundfile = await self.sound_queue.get()
                self.played_sounds.append(soundfile)  # Record for test verification
            except asyncio.CancelledError:
                break

    async def queue_word_sound(self, word: str, player: int) -> None:
        """Mock word sound queueing."""
        sound_file = f"mock_word_sounds_{player}/{word.lower()}.wav"
        self.played_sounds.append(f"queued: {sound_file}")

    def play_start(self) -> None:
        """Mock start sound."""
        self.played_sounds.append("start_sound")

    def play_crash(self) -> None:
        """Mock crash sound."""
        self.played_sounds.append("crash_sound")

    def play_chunk(self) -> None:
        """Mock chunk sound."""
        self.played_sounds.append("chunk_sound")

    def play_game_over(self) -> None:
        """Mock game over sound."""
        self.played_sounds.append("game_over_sound")

    def play_bloop(self) -> None:
        """Mock bloop sound."""
        self.played_sounds.append("bloop_sound")

    def get_played_sounds(self) -> List[str]:
        """Get list of sounds that were 'played' for test verification."""
        return self.played_sounds.copy()

    def clear_played_sounds(self) -> None:
        """Clear the played sounds list for fresh testing."""
        self.played_sounds.clear()