"""Domain models."""


class User:
    def __init__(self, username: str) -> None:
        self.username = username


def create_user(name: str) -> User:
    return User(name)
