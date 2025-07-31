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

    def on(self, event: str) -> Callable:
        if event not in self.listeners:
            self.listeners[event] = []

        def wrapper(func, *args):
            self.listeners[event].append(func)
            return func

        return wrapper

    # this function is purposefully not async
    # code calling this will do so in a "fire-and-forget" manner, and shouldn't be
    # slowed down by needing to await a result
    def trigger(self, event, *args, **kwargs):
        asyncio.create_task(self.async_trigger(event, *args, **kwargs), name=f"{event} handler")

    async def async_trigger(self, event, *args, **kwargs):
        logging.info(f"async_trigger: {event}")
        if event in self.listeners:
            # print(f"in list: {event}")
            
            for func in self.listeners[event]:
                await func(*args, **kwargs)
        else:
            raise Exception(f"async_trigger: no event {event} in {self.listeners}")

events = EventEngine()
