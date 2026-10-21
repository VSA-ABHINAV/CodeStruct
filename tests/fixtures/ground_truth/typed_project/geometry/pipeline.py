"""Pipeline invoking typed operations."""

from geometry.canvas import Canvas
from geometry.shapes import Circle


def execute_render(radius: float) -> float:
    circle = Circle(radius)
    canvas = Canvas()
    return canvas.draw(circle)
