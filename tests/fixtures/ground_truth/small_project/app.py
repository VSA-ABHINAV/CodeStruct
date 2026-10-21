"""Small project entry point."""

from math_ops import Multiplier, add


class Calculator(Multiplier):
    def compute(self, x: int, y: int) -> int:
        sum_val = add(x, y)
        return self.multiply(sum_val, 2)


def main() -> int:
    calc = Calculator()
    return calc.compute(5, 10)
