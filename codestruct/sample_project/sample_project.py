"""Sample project for CodeStruct analysis testing."""


class Animal:
    """Base class for all zoo animals."""

    def __init__(self, name, age):
        self.name = name
        self.age = age

    def speak(self):
        return "..."

    def describe(self):
        return f"{self.name} is {self.age} years old"


class Dog(Animal):
    """A dog."""

    def fetch(self, item):
        return f"{self.name} fetches the {item}"

    def speak(self):
        return "Woof!"


class Cat(Animal):
    """A cat."""

    def climb_tree(self):
        return f"{self.name} climbs a tree"

    def speak(self):
        return "Meow!"


class Zoo:
    """Holds a collection of animals."""

    def __init__(self):
        self.animals = []

    def add_animal(self, animal):
        self.animals.append(animal)


def build_zoo():
    """Construct a sample zoo."""
    zoo = Zoo()
    zoo.add_animal(Dog("Rex", 3))
    zoo.add_animal(Cat("Whiskers", 2))
    return zoo


def main():
    """Entry point."""
    zoo = build_zoo()
    for animal in zoo.animals:
        print(f"{animal.name} says {animal.speak()}")


if __name__ == "__main__":
    main()

