"""Base handler in core subpackage."""


class BaseHandler:
    def handle(self, payload: str) -> str:
        return f"handled:{payload}"
