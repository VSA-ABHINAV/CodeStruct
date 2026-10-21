"""API routing and orchestration layer."""

from ecommerce.domain.entities import Customer, Order, Product
from ecommerce.services.notification import Notifier
from ecommerce.services.order_service import OrderService
from ecommerce.services.pricing import DiscountPolicy
from ecommerce.storage.db import Database
from ecommerce.storage.repository import OrderRepository
from ecommerce.utils.config import load_config


def checkout(customer_name: str, email: str, prices: list[float]) -> float:
    config = load_config()
    discount_rate = config.get("default_discount", 0.0)

    cust = Customer(customer_name, email)
    items = [Product(f"item-{i}", p) for i, p in enumerate(prices)]
    order = Order(cust, items)

    policy = DiscountPolicy()
    notifier = Notifier()
    svc = OrderService(policy, notifier)
    final_price = svc.process_order(order, discount_rate)

    db = Database()
    repo = OrderRepository(db)
    repo.save_order(order)
    return final_price
