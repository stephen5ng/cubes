"""Screen recording logic for the game."""

import pygame
import os
import subprocess
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class GameRecorder(ABC):
    """Abstract base class for game screen recording."""

    @abstractmethod
    def trigger(self, now_ms: int) -> None:
        """Trigger a recording sequence starting from now."""
        pass

    @abstractmethod
    def capture(self, window: pygame.Surface, now_ms: int) -> None:
        """Capture a frame if recording is active."""
        pass


class NullRecorder(GameRecorder):
    """Null object implementation that does nothing."""

    def trigger(self, now_ms: int) -> None:
        pass

    def capture(self, window: pygame.Surface, now_ms: int) -> None:
        pass


class FileSystemRecorder(GameRecorder):
    """Records game frames to filesystem and generates movies."""

    def __init__(self, capture_dir: str = "capture"):
        self.capture_dir = capture_dir
        self.capture_frames_remaining = 0
        self.capture_sequence_id = 0
        self.sequence_frame_count = 0
        
        # Ensure capture directory exists
        os.makedirs(self.capture_dir, exist_ok=True)

    def trigger(self, now_ms: int) -> None:
        """Trigger a recording sequence."""
        if self.capture_frames_remaining == 0:
            self.capture_sequence_id = now_ms
            self.sequence_frame_count = 0
        self.capture_frames_remaining = 100
        logger.info(f"Triggering screenshot sequence {self.capture_sequence_id} starting at {now_ms}")

    def capture(self, window: pygame.Surface, now_ms: int) -> None:
        """Capture frame and generate movie if sequence complete."""
        if self.capture_frames_remaining > 0:
            filename = f"{self.capture_dir}/seq_{self.capture_sequence_id}_{self.sequence_frame_count:03d}.png"
            pygame.image.save(window, filename)
            self.sequence_frame_count += 1
            self.capture_frames_remaining -= 1
            
            if self.capture_frames_remaining == 0:
                logger.info(f"Screenshot sequence {self.capture_sequence_id} complete. Generating movie...")
                try:
                    cmd = (
                        f"ffmpeg -y -framerate 30 "
                        f"-i {self.capture_dir}/seq_{self.capture_sequence_id}_%03d.png "
                        f"-c:v libx264 -pix_fmt yuv420p "
                        f"{self.capture_dir}/collision_{self.capture_sequence_id}.mp4 "
                        f"&& rm {self.capture_dir}/seq_{self.capture_sequence_id}_*.png"
                    )
                    subprocess.Popen(cmd, shell=True)
                except Exception as e:
                    logger.error(f"Failed to generate movie: {e}")
