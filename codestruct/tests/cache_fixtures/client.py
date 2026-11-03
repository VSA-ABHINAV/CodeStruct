"""Client module for cache cross-file fixture (Phase 14)."""


class ApiClient:
    """API client consuming DatabaseService."""

    def __init__(self):
        self.db = None

    def initialize(self):
        """Construct database service and connect."""
        db = DatabaseService()
        db.connect()
        self.db = db
        return self.db
