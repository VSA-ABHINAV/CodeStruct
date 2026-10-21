"""Pricing and discount calculations."""

from ecommerce.domain.entities import Order


def calc_tax(subtotal: float) -> float:
    return subtotal * 0.10


class DiscountPolicy:
    def apply_discount(self, order: Order, rate: float) -> float:
        base_total = order.total()
        return base_total * (1.0 - rate)
