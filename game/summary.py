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
    habit: str = ""


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
        hit_flags=hit_flags, running_accuracy=running, habit=find_habit(records),
    )


def find_habit(records):
    """The clearest habit shown in this match, in one sentence."""
    moves = [r.player_move for r in records]
    best, best_score = None, 0.0

    # What follows a move: needs at least 3 examples, and the same answer at least 60% of the time
    after = {}
    for previous, following in zip(moves, moves[1:]):
        after.setdefault(previous, Counter())[following] += 1
    for previous, counts in after.items():
        total = sum(counts.values())
        move, count = counts.most_common(1)[0]
        if total >= 3 and count / total >= 0.6 and count * count / total > best_score:
            best_score = count * count / total
            best = f"After {previous} you threw {move} {count} of {total} times."

    if best:
        return best

    if len(moves) >= 6:
        move, count = Counter(moves).most_common(1)[0]
        if count / len(moves) >= 0.5:
            return f"You threw {move} {count} of {len(moves)} times."
    return "The AI found no strong habit: you were hard to read."
