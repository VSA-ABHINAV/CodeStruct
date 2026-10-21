"""Command-line interface entry point."""

from ecommerce.api.routes import checkout
from ecommerce.utils.logger import AuditLogger


def cli_main() -> int:
    logger = AuditLogger()
    logger.log_event("CLI initiated")
    total = checkout("Alice", "alice@example.com", [10.0, 25.5])
    logger.log_event(f"Checkout completed: {total}")
    return 0
