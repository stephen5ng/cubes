"""Fake MQTT client for unit and integration tests.

Unlike MockMqttClient (which replays pre-recorded events), FakeMqttClient
provides a simple test double for MQTT operations without needing recordings.
"""
import asyncio
from typing import List, Tuple


class FakeMqttClient:
    """Fake MQTT client that captures publish calls and allows injecting messages."""

    def __init__(self):
        self.published_messages: List[Tuple[str, str, bool]] = []
        self.subscriptions: List[str] = []
        self._message_queue: asyncio.Queue = asyncio.Queue()

    async def publish(self, topic: str, message: str, retain: bool = False) -> None:
        """Capture published messages for test verification."""
        self.published_messages.append((topic, message, retain))

    async def subscribe(self, topic: str) -> None:
        """Track subscriptions for test verification."""
        self.subscriptions.append(topic)

    async def inject_message(self, topic: str, payload: str) -> None:
        """Inject an incoming MQTT message for testing.

        This simulates receiving a message from the broker.
        """
        class FakeTopic:
            def __init__(self, value: str):
                self.value = value
            def __str__(self) -> str:
                return self.value
            def matches(self, pattern: str) -> bool:
                return self.value.startswith(pattern.replace('#', ''))

        class FakeMessage:
            def __init__(self, topic: str, payload: str):
                self.topic = FakeTopic(topic)
                self.payload = payload.encode() if payload else b""

        await self._message_queue.put(FakeMessage(topic, payload))

    @property
    def messages(self):
        """Return self as async iterator to match real MQTT client interface."""
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        """Async iterator that yields injected messages."""
        try:
            # Wait for next message with timeout to allow test to finish
            message = await asyncio.wait_for(self._message_queue.get(), timeout=0.1)
            return message
        except asyncio.TimeoutError:
            # Keep waiting unless we're done
            return await self.__anext__()

    def get_published(self, topic_prefix: str) -> List[Tuple[str, str, bool]]:
        """Get all published messages matching a topic prefix."""
        return [msg for msg in self.published_messages if msg[0].startswith(topic_prefix)]

    def clear_published(self) -> None:
        """Clear recorded published messages."""
        self.published_messages.clear()
