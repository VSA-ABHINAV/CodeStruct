"""Service module for cache cross-file fixture (Phase 14)."""


class DatabaseService:
    """A database service providing data access."""

    def __init__(self, connection_string: str = "sqlite:///:memory:"):
        self.connection_string = connection_string
        self.connected = False

    def connect(self) -> bool:
        """Establish database connection."""
        self.connected = True
        return True

    def query(self, sql: str) -> list:
        """Execute a query and return results."""
        if not self.connected:
            return []
        return [{"id": 1, "query": sql}]
