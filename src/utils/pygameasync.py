import asyncio
import logging
import pygame
from typing import Callable
from collections import defaultdict
from dataclasses import fields

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

    def trigger(self, event: any) -> None:
        """Trigger a typed event.

        Args:
            event: A GameEvent object with event_type and typed fields
        """
        if self.running:
            # Typed event - extract event name and convert fields to args
            event_name = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
            # Extract all fields except event_type as positional arguments
            event_args = tuple(getattr(event, f.name) for f in fields(event) if f.name != 'event_type')
            self.queue.put_nowait((event_name, event_args, {}))

    async def start(self) -> None:
        self.running = True
        asyncio.create_task(self._worker(), name="event_worker")

    async def stop(self) -> None:
        self.running = False
        try:
            await asyncio.wait_for(self.queue.join(), timeout=2.0)
        except asyncio.TimeoutError:
            logging.warning("Event queue join timed out, there may be unfinished tasks.")

    async def _worker(self) -> None:
        while self.running:
            try:
                event, args, kwargs = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                try:
                    for func in self.listeners[event]:
                        try:
                            await func(*args, **kwargs)
                        except Exception as e:
                            logging.error(f"Event handler error: {e}")
                finally:
                    self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Event worker error: {e}")
            except BaseException as e:
                logging.error(f"Event worker critical error: {e}")
                raise e


events = EventEngine()
