"""Auth service in services subpackage."""

from pkg.core.base import BaseHandler
from pkg.domain.models import User, create_user


class AuthService(BaseHandler):
    def login(self, username: str) -> User:
        user = create_user(username)
        _status = self.handle(username)
        return user
