"""Saved player profiles, stored as one JSON file."""
import json
import os
import time


class PlayerStore:
    def __init__(self, path):
        self.path = path

    def load_all(self):
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # Keep the unreadable file so a later save can't silently destroy it
            backup = f"{self.path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"
            try:
                os.replace(self.path, backup)
                print(f"WARNING: {self.path} was unreadable; moved to {backup}")
            except OSError:
                pass
            return {}

    def save_player(self, name, record):
        data = self.load_all()
        data[name] = {**record, "last_played": time.strftime("%Y-%m-%d %H:%M:%S")}
        # Write to a temp file then swap it in, so a crash mid-write can't corrupt the data
        tmp_file = self.path + ".tmp"
        with open(tmp_file, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_file, self.path)
