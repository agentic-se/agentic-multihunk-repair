"""Bird classes for the sample repo."""


class Bird:
    """Base class for all birds."""

    def __init__(self, name: str, wingspan: float):
        self.name = name
        self.wingspan = wingspan

    def speak(self) -> str:
        """Birds chirp."""
        return "Tweet!"

    def fly(self, distance: float) -> bool:
        """Whether the bird can fly the given distance (heuristic)."""
        return self.wingspan * 10 > distance
