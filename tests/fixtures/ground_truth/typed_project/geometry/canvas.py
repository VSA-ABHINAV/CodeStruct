"""Canvas for rendering shapes."""

from geometry.shapes import Shape


class Canvas:
    def draw(self, shape: Shape) -> float:
        return shape.area()
