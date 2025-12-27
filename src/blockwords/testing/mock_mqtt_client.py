import asyncio

class MockMqttClient:
    """Mock MQTT client for replay mode that feeds events to trigger_events_from_mqtt."""
    
    def __init__(self, replay_events):
        # Reverse MQTT events to maintain chronological order since they come in reversed from GameReplayer
        self.replay_events = list(reversed(replay_events))
        self.event_index = 0
        self.game_ready = False
    
    def set_game_ready(self):
        """Mark the game as ready to receive MQTT messages."""
        self.game_ready = True
    
    @property
    def messages(self):
        """Return self as an async iterator to match the real MQTT client interface."""
        return self
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        """Async iterator that yields MQTT messages from replay events."""
        # Wait for game to be ready before starting MQTT replay
        if not self.game_ready:
            await asyncio.sleep(0.1)  # Small delay to allow game initialization
            return await self.__anext__()
            
        if self.event_index >= len(self.replay_events):
            raise StopAsyncIteration
            
        event = self.replay_events[self.event_index]
        self.event_index += 1
        
        if event['event_type'] == 'mqtt_message':
            # Create mock MQTT message
            class MockTopic:
                def __init__(self, topic_str):
                    self.value = topic_str
                def __str__(self):
                    return self.value
                def matches(self, pattern):
                    return self.value.startswith(pattern.replace('#', ''))
            
            class MockMqttMessage:
                def __init__(self, topic_str, payload_str):
                    self.topic = MockTopic(topic_str)
                    self.payload = payload_str.encode() if payload_str else b""
            
            topic = event['data']['topic']
            payload = event['data']['payload']
            mock_message = MockMqttMessage(topic, payload)
            
            # Wait for the appropriate timestamp
            if self.event_index > 1:
                prev_timestamp = self.replay_events[self.event_index - 2]['timestamp_ms']
                current_timestamp = event['timestamp_ms']
                delay_ms = current_timestamp - prev_timestamp
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000.0)
            
            return mock_message
        else:
            # Skip non-MQTT events and continue to next
            return await self.__anext__()
