"""
Thread-safe event bus connecting simulation threads to the Pygame draw loop.
Events are plain dicts with a required "type" key.
"""
import queue
import time


class EventBus:
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self.speed: float = 1.0   # multiplier; S=0.5x, F=2x

    def post(self, event: dict) -> None:
        self._q.put(event)

    def poll(self) -> dict | None:
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds / max(self.speed, 0.1))
