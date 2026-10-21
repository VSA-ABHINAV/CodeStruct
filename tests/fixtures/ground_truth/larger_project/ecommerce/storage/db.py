"""Database persistence layer."""


class Database:
    def query(self, sql: str) -> list[dict[str, str]]:
        return [{"status": "success", "sql": sql}]
