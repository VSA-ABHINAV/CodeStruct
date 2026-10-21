"""Domain entities for ecommerce project."""


class Customer:
    def __init__(self, name: str, email: str) -> None:
        self.name = name
        self.email = email


class Product:
    def __init__(self, sku: str, price: float) -> None:
        self.sku = sku
        self.price = price


class Order:
    def __init__(self, customer: Customer, items: list[Product]) -> None:
        self.customer = customer
        self.items = items

    def total(self) -> float:
        return sum(item.price for item in self.items)
