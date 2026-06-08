"""Resource file: Two hunks in sibling methods of the same class."""

class Calculator:
    def __init__(self):
        self.total = 0

    def add(self, value):
        """Add a value to total."""
        self.total += value  # Hunk 1 will modify this line
        return self.total

    def subtract(self, value):
        """Subtract a value from total."""
        self.total -= value  # Hunk 2 will modify this line
        return self.total

    def reset(self):
        """Reset the total."""
        self.total = 0
