"""The AI opponent: four small predictors of the player's next move, weighted by how well each has done.

Each predictor counts habits with a decay, so old habits fade, and smooths its counts, so a few
observations cannot produce a confident guess:

    Frequency              how often the player throws each move
    Last move              what follows their previous move (first-order Markov)
    Last two moves         what follows their previous two moves (second-order Markov)
    Win-stay / lose-shift  whether they repeat or change after a win, a loss or a tie

The AI picks its move by expected score against the blended prediction, with some randomness
when the edge is small so it cannot be exploited by playing against its rhythm.
"""
import math
import random
from dataclasses import dataclass, field

import numpy as np

import config

CHOICES = ["ROCK", "PAPER", "SCISSORS"]
INDEX = {move: i for i, move in enumerate(CHOICES)}
BEATS = {"ROCK": "SCISSORS", "PAPER": "ROCK", "SCISSORS": "PAPER"}
COUNTERS = {"ROCK": "PAPER", "PAPER": "SCISSORS", "SCISSORS": "ROCK"}  # the move that beats the key

OUTCOMES = ["WIN", "LOSE", "TIE"]  # from the player's side

MODE_PREDICTIVE = "Predictive"
MODE_RANDOM = "Random"

EXPERT_FREQUENCY = "Frequency"
EXPERT_LAST_MOVE = "Last move"
EXPERT_LAST_TWO = "Last two moves"
EXPERT_WSLS = "Win-stay / lose-shift"
EXPERT_NAMES = [EXPERT_FREQUENCY, EXPERT_LAST_MOVE, EXPERT_LAST_TWO, EXPERT_WSLS]

STATE_VERSION = 2


def outcome_for_player(player_move, ai_move):
    if player_move == ai_move:
        return "TIE"
    return "WIN" if BEATS[player_move] == ai_move else "LOSE"


@dataclass
class Prediction:
    probs: dict          # what the AI expects the player to throw
    evidence: str        # "LOW" | "MEDIUM" | "HIGH"
    top_expert: str      # which pattern the AI trusts most
    ai_move: str
    weights: dict = field(default_factory=dict)  # how much each expert counted
    samples: float = 0.0                         # observations behind the lead expert's guess
    expected: str = None                         # the move the AI thinks you will throw (None if it is guessing)
    reason: str = ""                             # why, in plain words ("" if no single habit explains it)


def explain(prediction, player_move):
    """One sentence on what the AI expected this round and what happened."""
    if player_move not in CHOICES:
        return "No hand was detected, so the AI learned nothing this round."
    if prediction.top_expert == "Random":
        return "Random mode: the AI just guessed."
    if prediction.expected is None:
        if prediction.top_expert == "No history yet":
            return "First throw of this session: the AI had nothing to go on, so it guessed."
        return "No move stood out in your throws yet, so the AI played almost at random."

    percent = round(prediction.probs[prediction.expected] * 100)
    early = ", an early guess" if prediction.evidence == "LOW" else ""
    why = f" because {prediction.reason}" if prediction.reason else " from a mix of your habits"
    counter = COUNTERS[prediction.expected]
    if prediction.ai_move == counter:
        played = f", so it played {counter}"
    else:
        played = f", so it leaned towards {counter} but played {prediction.ai_move} to stay unpredictable"
    sentence = f"The AI expected {prediction.expected} ({percent}%{early}){why}{played}."
    if player_move == prediction.expected:
        return sentence + " You threw it."
    sentence += f" But you threw {player_move}."
    return sentence + (" You broke your pattern!" if percent >= 60 and prediction.evidence != "LOW" else "")


def _smooth(row):
    return (row + config.AI_SMOOTHING) / (row.sum() + 3 * config.AI_SMOOTHING)


class AdaptiveEngine:
    def __init__(self, mode=MODE_PREDICTIVE, rng=None):
        self.mode = mode
        self.rng = rng or random.Random()
        self.reset()

    # ---- memory -------------------------------------------------------------------------------

    def reset(self):
        """Forget everything: a new visitor."""
        self.freq = np.zeros(3)
        self.m1 = np.zeros((3, 3))          # [last][next]
        self.m2 = np.zeros((3, 3, 3))       # [two moves ago][last][next]
        self.wsls = np.zeros((3, 3))        # [last outcome][0 = stay, 1 = next in cycle, 2 = previous in cycle]
        self.scores = {name: 0.0 for name in EXPERT_NAMES}
        self.rounds_seen = 0
        self._forget_recent_moves()

    def _forget_recent_moves(self):
        """A new session starts with no previous move, even for a returning player."""
        self.last1 = self.last2 = self.last_outcome = None

    @property
    def last_move(self):
        return None if self.last1 is None else CHOICES[self.last1]

    def toggle_mode(self):
        self.mode = MODE_RANDOM if self.mode == MODE_PREDICTIVE else MODE_PREDICTIVE

    # ---- prediction ---------------------------------------------------------------------------

    def _predictions(self):
        """{expert: (probabilities over the player's next move, observations behind it)}"""
        found = {EXPERT_FREQUENCY: (_smooth(self.freq), self.freq.sum())}
        if self.last1 is None:
            return found
        found[EXPERT_LAST_MOVE] = (_smooth(self.m1[self.last1]), self.m1[self.last1].sum())
        if self.last2 is not None:
            row = self.m2[self.last2, self.last1]
            found[EXPERT_LAST_TWO] = (_smooth(row), row.sum())
        if self.last_outcome is not None:
            row = self.wsls[self.last_outcome]
            shifts = _smooth(row)
            probs = np.zeros(3)
            for shift in range(3):
                probs[(self.last1 + shift) % 3] = shifts[shift]
            found[EXPERT_WSLS] = (probs, row.sum())
        return found

    def _weights(self, names):
        top = max(self.scores[n] for n in names)
        raw = {n: math.exp(config.AI_TRUST_SHARPNESS * (self.scores[n] - top)) for n in names}
        total = sum(raw.values())
        return {n: v / total for n, v in raw.items()}

    def lock_move(self):
        """Choose the AI's move. Called before the player's throw is read."""
        if self.mode == MODE_RANDOM or self.rounds_seen == 0:
            uniform = {move: 1 / 3 for move in CHOICES}
            expert = "Random" if self.mode == MODE_RANDOM else "No history yet"
            return Prediction(uniform, "LOW", expert, self.rng.choice(CHOICES))

        found = self._predictions()
        weights = self._weights(list(found))
        blended = sum(weights[n] * found[n][0] for n in found)
        top = max(found, key=lambda n: (weights[n], found[n][1]))

        samples = found[top][1]
        evidence = ("HIGH" if samples >= config.EVIDENCE_HIGH
                    else "MEDIUM" if samples >= config.EVIDENCE_MEDIUM else "LOW")
        probs = {move: float(blended[i]) for i, move in enumerate(CHOICES)}
        ranked = sorted(CHOICES, key=lambda move: -probs[move])
        expected = ranked[0]
        own_pick = CHOICES[int(np.argmax(found[top][0]))]
        reason = self._reason(top, found[top][0]) if own_pick == expected else ""
        if probs[ranked[0]] - probs[ranked[1]] < config.AI_CLEAR_MARGIN:
            expected, reason = None, ""   # no move stands out, so the AI is only guessing
        return Prediction(probs, evidence, top, self._choose(blended), weights, samples, expected, reason)

    def _reason(self, expert, probs):
        """The habit behind the lead expert's guess, in a few words."""
        move = CHOICES[int(np.argmax(probs))].lower()
        if expert == EXPERT_FREQUENCY:
            return f"you throw {move} most often"
        if expert == EXPERT_LAST_MOVE:
            return f"you often throw {move} after {self.last_move.lower()}"
        if expert == EXPERT_LAST_TWO:
            return f"you often throw {move} after {CHOICES[self.last2].lower()} then {self.last_move.lower()}"
        return f"after a {('win', 'loss', 'draw')[self.last_outcome]} you tend to throw {move}"

    def _choose(self, blended):
        """Pick by expected score. Close calls stay close to random, strong patterns get exploited."""
        payoffs = [blended[INDEX[BEATS[move]]] - blended[INDEX[COUNTERS[move]]] for move in CHOICES]
        best = max(payoffs)
        weights = [math.exp(config.AI_SOFTMAX_K * (p - best)) for p in payoffs]
        return self.rng.choices(CHOICES, weights=weights)[0]

    # ---- learning -----------------------------------------------------------------------------

    def observe(self, player_move, ai_move=None):
        """Learn from the player's throw. A move that wasn't detected (None) teaches nothing."""
        if player_move not in CHOICES:
            return
        actual = INDEX[player_move]

        # Grade every expert on this round before it learns from it
        for name, (probs, _) in self._predictions().items():
            self.scores[name] = (config.AI_SCORE_FORGET * self.scores[name]
                                 + math.log(3 * probs[actual]))

        for table in (self.freq, self.m1, self.m2, self.wsls):
            table *= config.AI_DECAY
        self.freq[actual] += 1
        if self.last1 is not None:
            self.m1[self.last1, actual] += 1
            if self.last2 is not None:
                self.m2[self.last2, self.last1, actual] += 1
            if self.last_outcome is not None:
                self.wsls[self.last_outcome, (actual - self.last1) % 3] += 1

        self.last2 = self.last1
        self.last1 = actual
        self.last_outcome = None if ai_move is None else OUTCOMES.index(outcome_for_player(player_move, ai_move))
        self.rounds_seen += 1

    # ---- saving -------------------------------------------------------------------------------

    def to_dict(self):
        return {
            "version": STATE_VERSION,
            "rounds_seen": self.rounds_seen,
            "freq": self.freq.tolist(),
            "m1": self.m1.tolist(),
            "m2": self.m2.tolist(),
            "wsls": self.wsls.tolist(),
            "scores": dict(self.scores),
        }

    def load_record(self, record):
        """Restore a player's memory from a saved profile. Understands the older format too."""
        self.reset()
        if not record:
            return
        try:
            if record.get("engine", {}).get("version") == STATE_VERSION:
                self._load_state(record["engine"])
                return
        except (KeyError, ValueError, TypeError, AttributeError):
            self.reset()
        self._load_legacy(record.get("transitions") or {})

    def _load_state(self, state):
        freq = np.array(state["freq"], dtype=float)
        m1 = np.array(state["m1"], dtype=float)
        m2 = np.array(state["m2"], dtype=float)
        wsls = np.array(state["wsls"], dtype=float)
        if freq.shape != (3,) or m1.shape != (3, 3) or m2.shape != (3, 3, 3) or wsls.shape != (3, 3):
            raise ValueError("saved AI memory has the wrong shape")
        self.freq, self.m1, self.m2, self.wsls = freq, m1, m2, wsls
        self.scores = {name: float(state["scores"].get(name, 0.0)) for name in EXPERT_NAMES}
        self.rounds_seen = int(state["rounds_seen"])

    def _load_legacy(self, transitions):
        """The first version stored counts that started at 1 for every move."""
        for last, row in transitions.items():
            if last not in INDEX or not isinstance(row, dict):
                continue
            for nxt, count in row.items():
                if nxt in INDEX:
                    self.m1[INDEX[last], INDEX[nxt]] = max(0.0, float(count) - 1)
        self.freq = self.m1.sum(axis=0)
        self.rounds_seen = int(self.m1.sum())

    def legacy_transitions(self):
        """The same habits in the first version's format, so rps_game.py can still read the save."""
        return {
            move: {nxt: int(round(self.m1[i, j])) + 1 for j, nxt in enumerate(CHOICES)}
            for i, move in enumerate(CHOICES) if self.m1[i].sum() > 0
        }


MarkovEngine = AdaptiveEngine  # earlier name
