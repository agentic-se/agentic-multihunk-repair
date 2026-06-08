"""Mammal classes for the sample repo."""
from typing import List


class Mammal:
    """Base class for all mammals."""

    def __init__(self, name: str, weight: float):
        self.name = name
        self.weight = weight

    def speak(self) -> str:
        """Return a generic mammal sound."""
        return "some mammal sound"

    def list_traits(self) -> List[str]:
        """Return characteristic traits of mammals."""
        return ["warm-blooded", "hair"]


class Dog(Mammal):
    """Domestic dog, subclass of Mammal."""

    def speak(self) -> str:
        """Dogs bark."""
        return "Woof!"

    def fetch(self, item: str) -> str:
        """Bring an item back to the owner."""
        return f"{self.name} fetches the {item}"
