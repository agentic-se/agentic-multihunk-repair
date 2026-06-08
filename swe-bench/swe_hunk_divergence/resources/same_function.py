"""Resource file: Two hunks in the same function."""

def calculate_total(items):
    """Calculate total price with tax."""
    subtotal = 0
    for item in items:
        subtotal += item.price  # Hunk 1 will modify this line

    tax_rate = 0.08
    tax = subtotal * tax_rate  # Hunk 2 will modify this line

    total = subtotal + tax
    return total
