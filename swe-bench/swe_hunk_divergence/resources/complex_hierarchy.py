"""Resource file: Complex class hierarchy for advanced AST distance testing."""

class BaseService:
    def __init__(self):
        self.config = {}  # Hunk 1 will modify this line

    def configure(self, key, value):
        self.config[key] = value


class DataService(BaseService):
    def __init__(self):
        super().__init__()
        self.cache = {}

    def fetch_data(self, key):
        """Fetch data with caching."""
        if key in self.cache:
            return self.cache[key]  # Hunk 2 will modify this line

        data = self._load_from_db(key)
        self.cache[key] = data
        return data

    def _load_from_db(self, key):
        """Load from database."""
        return {"id": key, "value": None}  # Hunk 3 will modify this line
