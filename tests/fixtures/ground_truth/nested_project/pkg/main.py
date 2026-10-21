"""Nested project main entrypoint."""

from pkg.services.auth import AuthService
from pkg.utils.formatting import format_name


def run_app(raw_name: str) -> str:
    cleaned = format_name(raw_name)
    auth = AuthService()
    user = auth.login(cleaned)
    return user.username
