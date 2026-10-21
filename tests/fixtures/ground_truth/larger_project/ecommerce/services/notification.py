"""Notification service."""

from ecommerce.domain.events import OrderPlacedEvent


class Notifier:
    def notify(self, event: OrderPlacedEvent) -> bool:
        return event.amount > 0
