"""Resource file: Two hunks in different classes."""

class UserManager:
    def __init__(self):
        self.users = []

    def add_user(self, user):
        """Add a user to the system."""
        self.users.append(user)  # Hunk 1 will modify this line
        return len(self.users)


class ProductManager:
    def __init__(self):
        self.products = []

    def add_product(self, product):
        """Add a product to inventory."""
        self.products.append(product)  # Hunk 2 will modify this line
        return len(self.products)
