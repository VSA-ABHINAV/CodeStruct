"""Fixture for Factory design pattern detection (Phase 13)."""


class Circle:
    """A circular geometric shape."""

    def __init__(self, radius: float = 1.0):
        self.radius = radius


class Square:
    """A square geometric shape."""

    def __init__(self, side: float = 1.0):
        self.side = side


def create_shape(shape_type: str):
    """Factory function constructing distinct shapes across conditional branches."""
    if shape_type == "circle":
        return Circle()
    elif shape_type == "square":
        return Square()
    else:
        return None
