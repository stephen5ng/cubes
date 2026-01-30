import asyncio
import pygame
import logging
from typing import List, Dict, Any, Optional
from testing.game_replayer import GameReplayer

logger = logging.getLogger(__name__)

class InputManager:
    """Centralizes all input event collection and distribution."""

    def __init__(self, replay_file: str = ""):
        self.replay_file = replay_file
        self.replayer: Optional[GameReplayer] = None
        
        if self.replay_file:
            self.replayer = GameReplayer(self.replay_file)
            self.replayer.load_events()

    def get_pygame_events(self) -> List[Dict[str, Any]]:
        """Collect pygame events (KEYDOWN, QUIT, JOYAXISMOTION, etc.)"""
        pygame_events = []
        for pygame_event in pygame.event.get():
            if pygame_event.type == pygame.QUIT:
                pygame_events.append({"type": "QUIT"})
            elif pygame_event.type == pygame.KEYDOWN:
                pygame_events.append({
                    "type": "KEYDOWN",
                    "key": pygame.key.name(pygame_event.key).upper()
                })
            elif pygame_event.type == pygame.JOYAXISMOTION:
                pygame_events.append({
                    "type": "JOYAXISMOTION",
                    "axis": pygame_event.axis,
                    "value": pygame_event.value
                })
            elif pygame_event.type == pygame.JOYBUTTONDOWN:
                pygame_events.append({
                    "type": "JOYBUTTONDOWN",
                    "button": pygame_event.button,
                })
        return pygame_events

    def get_mqtt_events(self, mqtt_message_queue: asyncio.Queue) -> List[Dict[str, Any]]:
        """Drain MQTT queue into event list."""
        mqtt_events = []
        try:
            while not mqtt_message_queue.empty():
                mqtt_message = mqtt_message_queue.get_nowait()
                event = {
                    'topic': str(mqtt_message.topic),
                    'payload': mqtt_message.payload.decode() if mqtt_message.payload else None
                }
                mqtt_events.append(event)
        except asyncio.QueueEmpty:
            pass
        return mqtt_events

    def get_replay_events(self, pygame_events: List[Dict], mqtt_events: List[Dict]) -> int:
        """Get next replay frame (pygame_events, mqtt_events, timestamp_ms)."""
        if not self.replayer or not self.replayer.events:
            return 0
            
        replay_events = self.replayer.events.pop()
        now_ms = replay_events['timestamp_ms']
        
        if 'events' in replay_events:
            events_data = replay_events['events']
            if 'pygame' in events_data:
                pygame_events.extend(events_data['pygame'])
            if 'mqtt' in events_data:
                mqtt_events.extend(events_data['mqtt'])
                
        return now_ms

    def has_replay_events_remaining(self) -> bool:
        """Check if replay has more events."""
        return bool(self.replayer and self.replayer.events)
