import asyncio
import logging
import pygame
from typing import Callable
from collections import defaultdict

class Clock:
    def __init__(self, time_func: Callable[[], int] = pygame.time.get_ticks) -> None:
        self.time_func = time_func
        self.last_tick = time_func() or 0

    async def tick(self, fps: int = 0) -> None:
        if fps <= 0:
            return

        end_time = (1.0 / fps) * 1000
        current = self.time_func()
        time_diff = current - self.last_tick
        delay = max(0, (end_time - time_diff) / 1000)

        self.last_tick = current
        await asyncio.sleep(delay)

class EventEngine:
    def __init__(self) -> None:
        self.listeners: dict[str, list[Callable]] = defaultdict(list)
        self.queue: asyncio.Queue = asyncio.Queue()
        self.running = False

    def on(self, event: str) -> Callable:
        def wrapper(func: Callable) -> Callable:
            self.listeners[event].append(func)
            return func
        return wrapper

    def trigger(self, event: str, *args, **kwargs) -> None:
        if self.running:
            self.queue.put_nowait((event, args, kwargs))

    async def start(self) -> None:
        self.running = True
        asyncio.create_task(self._worker(), name="event_worker")

    async def stop(self) -> None:
        self.running = False
        await self.queue.join() 

    async def _worker(self) -> None:
        while self.running:
            try:
                event, args, kwargs = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                for func in self.listeners[event]:
                    try:
                        await func(*args, **kwargs)
                    except Exception as e:
                        logging.error(f"Event handler error: {e}")
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logging.error(f"Event worker error: {e}")


events = EventEngine()
