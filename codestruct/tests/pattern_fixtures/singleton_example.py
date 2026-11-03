"""Fixture for Singleton design pattern detection (Phase 13)."""


class DatabaseConnection:
    """A singleton database connection pool."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
