"""Audit logger utility."""


class AuditLogger:
    def log_event(self, message: str) -> str:
        return f"[AUDIT] {message}"
