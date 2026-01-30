import pytest
import asyncio
from unittest.mock import MagicMock, patch
import pygame
from input.input_manager import InputManager

@patch('pygame.event.get')
def test_get_pygame_events(mock_get):
    # Setup mock event
    mock_event = MagicMock()
    # Mocking type attribute on MagicMock can be tricky if it conflicts with internal methods
    # But for a simple attribute access it is fine
    mock_event.type = pygame.KEYDOWN
    mock_event.key = pygame.K_a
    mock_get.return_value = [mock_event]
    
    # Initialize pygame for constants if needed, though we imported it
    # pygame.init() # Not strictly necessary if we mock event.get
    
    manager = InputManager()
    events = manager.get_pygame_events()
    
    assert len(events) == 1
    assert events[0]['type'] == 'KEYDOWN'
    assert events[0]['key'] == 'A'

@pytest.mark.asyncio
async def test_get_mqtt_events():
    manager = InputManager()
    queue = asyncio.Queue()
    
    # Mock specific message object
    message = MagicMock()
    message.topic = "test/topic"
    message.payload = b"payload"
    await queue.put(message)
    
    events = manager.get_mqtt_events(queue)
    
    assert len(events) == 1
    assert events[0]['topic'] == "test/topic"
    assert events[0]['payload'] == "payload"
