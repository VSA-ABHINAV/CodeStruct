"""Domain events for ecommerce."""


class OrderPlacedEvent:
    def __init__(self, order_id: str, amount: float) -> None:
        self.order_id = order_id
        self.amount = amount
