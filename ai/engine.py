"""The AI opponent. Currently a first-order Markov chain over the player's moves."""
import random
from dataclasses import dataclass

CHOICES = ["ROCK", "PAPER", "SCISSORS"]
COUNTERS = {"ROCK": "PAPER", "PAPER": "SCISSORS", "SCISSORS": "ROCK"}

MODE_PREDICTIVE = "Predictive"
MODE_RANDOM = "Random"


@dataclass
class Prediction:
    probs: dict          # what the AI expects the player to throw
    evidence: str        # "LOW" | "MEDIUM" | "HIGH"
    top_expert: str      # which pattern the AI trusts most
    ai_move: str


def _new_row():
    return {move: 1 for move in CHOICES}


class MarkovEngine:
    def __init__(self, mode=MODE_PREDICTIVE, rng=None):
        self.mode = mode
        self.rng = rng or random.Random()
        self.transitions = {}
        self.last_move = None

    def load(self, saved_transitions=None):
        """Replace the AI's memory with a player's saved transition counts."""
        self.transitions = {}
        self.last_move = None
        for move, counts in (saved_transitions or {}).items():
            self.transitions[move] = {**_new_row(), **counts}

    def to_dict(self):
        return {move: dict(row) for move, row in self.transitions.items()}

    def toggle_mode(self):
        self.mode = MODE_RANDOM if self.mode == MODE_PREDICTIVE else MODE_PREDICTIVE

    def lock_move(self):
        """Choose the AI's move. Called before the player's throw is read."""
        if self.mode == MODE_RANDOM or self.last_move is None:
            uniform = {move: 1 / 3 for move in CHOICES}
            expert = "Random" if self.mode == MODE_RANDOM else "No history yet"
            return Prediction(uniform, "LOW", expert, self.rng.choice(CHOICES))

        row = self.transitions.get(self.last_move) or _new_row()
        total = sum(row.values())
        probs = {move: row[move] / total for move in CHOICES}
        predicted = max(row, key=lambda move: row[move] + self.rng.uniform(0, 0.1))
        observations = total - len(CHOICES)
        evidence = "LOW" if observations < 5 else "MEDIUM" if observations < 15 else "HIGH"
        return Prediction(probs, evidence, "First-order Markov", COUNTERS[predicted])

    def observe(self, player_move):
        """Learn from the player's throw. None means no move was detected."""
        if player_move not in CHOICES:
            return
        if self.last_move is not None:
            self.transitions.setdefault(self.last_move, _new_row())[player_move] += 1
        self.last_move = player_move
