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

    def _write(self, data):
        # Write to a temp file then swap it in, so a crash mid-write can't corrupt the data
        tmp_file = self.path + ".tmp"
        with open(tmp_file, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_file, self.path)

    def save_player(self, name, record):
        """Merge `record` into the player's profile, so fields it doesn't mention (like best_match) are kept."""
        data = self.load_all()
        data[name] = {**data.get(name, {}), **record, "last_played": time.strftime("%Y-%m-%d %H:%M:%S")}
        self._write(data)

    def clear_best_matches(self):
        """Wipe the leaderboard. Profiles, and what the AI learned about each player, stay."""
        data = self.load_all()
        for profile in data.values():
            profile.pop("best_match", None)
        self._write(data)
