import asyncio
import logging
import pygame
from typing import Callable

class Clock:
    def __init__(self, time_func: Callable=pygame.time.get_ticks) -> None:
        self.time_func = time_func
        self.last_tick = time_func() or 0

    async def tick(self, fps=0) -> None:
        if 0 >= fps:
            return

        end_time = (1.0 / fps) * 1000
        current = self.time_func()
        time_diff = current - self.last_tick
        delay = (end_time - time_diff) / 1000

        self.last_tick = current
        if delay < 0:
            delay = 0

        await asyncio.sleep(delay)

class EventEngine:
    def __init__(self) -> None:
        self.listeners: dict[str, list[Callable]] = {}
        self.queue = asyncio.Queue()
        self.running = False

    def on(self, event: str) -> Callable:
        if event not in self.listeners:
            self.listeners[event] = []

        def wrapper(func, *args):
            self.listeners[event].append(func)
            return func
        return wrapper

    def trigger(self, event, *args, **kwargs):
        if self.running:
            self.queue.put_nowait((event, args, kwargs))

    async def start(self):
        self.running = True
        asyncio.create_task(self._worker(), name="event_worker")

    async def stop(self):
        self.running = False

    async def _worker(self):
        while self.running:
            try:
                event, args, kwargs = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                if event in self.listeners:
                    for func in self.listeners[event]:
                        try:
                            await func(*args, **kwargs)
                        except Exception as e:
                            logging.error(f"Event handler error: {e}")
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logging.error(f"Event worker error: {e}")

events = EventEngine()

