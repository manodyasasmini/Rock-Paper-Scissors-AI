"""Operator settings (Ctrl+A in the game). Defaults come from config.py; changes are saved to a JSON file."""
import json
import os

import config


class Settings:
    def __init__(self, path=None):
        self.path = path
        self.match_rounds = config.MATCH_ROUNDS
        self.learn_mode = config.LEARN_MODE_DEFAULT
        self.skeleton_only = False
        self.sound = True
        self.idle_seconds = config.IDLE_SECONDS
        self._load()

    def _load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return  # keep the defaults; the next save replaces the unreadable file
        if data.get("match_rounds") in config.MATCH_ROUND_CHOICES:
            self.match_rounds = data["match_rounds"]
        if isinstance(data.get("learn_mode"), bool):
            self.learn_mode = data["learn_mode"]
        if isinstance(data.get("skeleton_only"), bool):
            self.skeleton_only = data["skeleton_only"]
        if isinstance(data.get("sound"), bool):
            self.sound = data["sound"]
        if data.get("idle_seconds") in config.IDLE_SECOND_CHOICES:
            self.idle_seconds = data["idle_seconds"]

    def save(self):
        if not self.path:
            return
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"match_rounds": self.match_rounds, "learn_mode": self.learn_mode,
                       "skeleton_only": self.skeleton_only, "sound": self.sound,
                       "idle_seconds": self.idle_seconds}, f, indent=2)
        os.replace(tmp, self.path)

    @staticmethod
    def _next(choices, current):
        return choices[(choices.index(current) + 1) % len(choices)] if current in choices else choices[0]

    def cycle_match_rounds(self):
        self.match_rounds = self._next(config.MATCH_ROUND_CHOICES, self.match_rounds)

    def cycle_idle_seconds(self):
        self.idle_seconds = self._next(config.IDLE_SECOND_CHOICES, self.idle_seconds)
