"""Order processing service orchestrating domain and notifications."""

from ecommerce.domain.entities import Order
from ecommerce.domain.events import OrderPlacedEvent
from ecommerce.services.notification import Notifier
from ecommerce.services.pricing import DiscountPolicy, calc_tax


class OrderService:
    def __init__(self, policy: DiscountPolicy, notifier: Notifier) -> None:
        self.policy = policy
        self.notifier = notifier

    def process_order(self, order: Order, rate: float) -> float:
        discounted = self.policy.apply_discount(order, rate)
        tax = calc_tax(discounted)
        final_amount = discounted + tax
        event = OrderPlacedEvent("ord-1", final_amount)
        self.notifier.notify(event)
        return final_amount
