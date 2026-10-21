"""Repository layer for persisting orders."""

from ecommerce.domain.entities import Order
from ecommerce.storage.db import Database


class OrderRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_order(self, order: Order) -> None:
        amount = order.total()
        self.db.query(f"INSERT INTO orders VALUES ({amount})")
