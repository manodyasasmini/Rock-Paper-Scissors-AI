"""What the AI learned about the player over one match. Pure data, no drawing."""
from collections import Counter
from dataclasses import dataclass, field

CHANCE = 1 / 3


@dataclass
class RoundRecord:
    player_move: str
    ai_move: str
    result: str            # "PLAYER", "AI" or "TIE"
    expected: str = None   # the move the AI expected, or None if it was guessing
    expected_prob: float = 0.0


@dataclass
class MatchSummary:
    rounds: int
    wins: int
    losses: int
    ties: int
    headline: str                                    # "YOU WIN", "AI WINS" or "DRAW"
    predicted_rounds: int                            # rounds where the AI had a real prediction
    hits: int                                        # of those, how many it got right
    accuracy: float                                  # hits / predicted_rounds (0 if none)
    hit_flags: list = field(default_factory=list)    # one per predicted round
    running_accuracy: list = field(default_factory=list)
    habits: list = field(default_factory=list)       # up to three, clearest first

    @property
    def habit(self):
        return self.habits[0] if self.habits else ""


def summarize(records):
    wins = sum(r.result == "PLAYER" for r in records)
    losses = sum(r.result == "AI" for r in records)
    ties = sum(r.result == "TIE" for r in records)
    headline = "YOU WIN" if wins > losses else "AI WINS" if losses > wins else "DRAW"

    hit_flags = [r.player_move == r.expected for r in records if r.expected is not None]
    running = [sum(hit_flags[:i + 1]) / (i + 1) for i in range(len(hit_flags))]
    return MatchSummary(
        rounds=len(records), wins=wins, losses=losses, ties=ties, headline=headline,
        predicted_rounds=len(hit_flags), hits=sum(hit_flags),
        accuracy=sum(hit_flags) / len(hit_flags) if hit_flags else 0.0,
        hit_flags=hit_flags, running_accuracy=running, habits=find_habits(records),
    )


NO_HABIT = "The AI found no strong habit: you were hard to read."


def find_habits(records, limit=3):
    """The clearest habits shown in this match, one sentence each, strongest first."""
    moves = [r.player_move for r in records]
    found = []

    # What follows a move: needs at least 3 examples, and the same answer at least 60% of the time
    after = {}
    for previous, following in zip(moves, moves[1:]):
        after.setdefault(previous, Counter())[following] += 1
    for previous, counts in after.items():
        total = sum(counts.values())
        move, count = counts.most_common(1)[0]
        if total >= 3 and count / total >= 0.6:
            found.append((count * count / total, f"After {previous} you threw {move} {count} of {total} times."))
    found.sort(key=lambda item: -item[0])
    habits = [sentence for _, sentence in found]

    if len(moves) >= 6:
        move, count = Counter(moves).most_common(1)[0]
        if count / len(moves) >= 0.5:
            habits.append(f"You threw {move} {count} of {len(moves)} times.")
    return habits[:limit] or [NO_HABIT]


def find_habit(records):
    """The single clearest habit."""
    return find_habits(records, 1)[0]


# How readable a player was, by the share of their throws the AI predicted
TITLES = [("MASTERMIND", "0 – 35%", 35), ("HARD TO READ", "36 – 50%", 50),
          ("CREATURE OF HABIT", "51 – 65%", 65), ("OPEN BOOK", "66%+", 100)]
MIN_ROUNDS_FOR_TITLE = 3


def title_index(summary):
    """Index into TITLES, or None when the AI made too few predictions to say."""
    if summary.predicted_rounds < MIN_ROUNDS_FOR_TITLE:
        return None
    percent = round(summary.accuracy * 100)
    return next(i for i, (_, _, upper) in enumerate(TITLES) if percent <= upper)
