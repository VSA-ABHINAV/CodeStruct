"""Shapes with stub-backed interface."""

from geometry.stubs import Renderable


class Shape(Renderable):
    def area(self) -> float:
        return 0.0


class Circle(Shape):
    def __init__(self, radius: float) -> None:
        self.radius = radius

    def area(self) -> float:
        return 3.14159 * self.radius * self.radius
