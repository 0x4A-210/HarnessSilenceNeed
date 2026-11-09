class RunCache:
    """Per-run cache only. Entries never cross input snapshots."""

    def __init__(self):
        self.entries = {}
        self.hits = 0

    def get(self, key):
        if key in self.entries:
            self.hits += 1
            return self.entries[key]
        return None

    def put(self, key, value):
        self.entries[key] = value
        return value
