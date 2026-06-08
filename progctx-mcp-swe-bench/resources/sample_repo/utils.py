"""Utility functions used across the sample repo."""


def normalize_name(name: str) -> str:
    """Strip whitespace and lower-case a name."""
    return name.strip().lower()


def compute_weight_kg(grams: float) -> float:
    """Convert grams to kilograms."""
    return grams / 1000.0
