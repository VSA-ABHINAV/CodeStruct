"""Fixture for Observer design pattern detection (Phase 13)."""


class Observer:
    """Base observer interface."""

    def update(self, message: str) -> None:
        pass


class EventDispatcher:
    """Subject / Publisher in the Observer pattern."""

    def __init__(self):
        self.subscribers = []

    def subscribe(self, observer: Observer) -> None:
        self.subscribers.append(observer)

    def notify(self, message: str) -> None:
        """Notify all subscribed observers."""
        for sub in self.subscribers:
            sub.update(message)
