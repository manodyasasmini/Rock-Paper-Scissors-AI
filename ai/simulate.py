"""Plays the AI against scripted players to measure how well it learns.

    python -m ai.simulate            compare the new engine with the first version's
    python -m ai.simulate --rounds 30 --games 500
"""
import argparse
import math
import random
import statistics
from dataclasses import dataclass

from ai.engine import BEATS, CHOICES, COUNTERS, INDEX, AdaptiveEngine, outcome_for_player


# ---- scripted players: each returns the next move given what has happened so far -------------

class RandomPlayer:
    name = "Random"

    def __init__(self, rng):
        self.rng = rng

    def move(self, history):
        return self.rng.choice(CHOICES)


class BiasedPlayer:
    name = "Favours rock (60%)"

    def __init__(self, rng):
        self.rng = rng

    def move(self, history):
        return self.rng.choices(CHOICES, weights=[0.6, 0.2, 0.2])[0]


class CyclePlayer:
    name = "Cycles R-P-S"

    def __init__(self, rng):
        self.start = rng.randrange(3)

    def move(self, history):
        return CHOICES[(self.start + len(history)) % 3]


class RepeatPatternPlayer:
    name = "Repeats R-R-P"

    def __init__(self, rng):
        self.start = rng.randrange(3)

    def move(self, history):
        return ["ROCK", "ROCK", "PAPER"][(self.start + len(history)) % 3]


class WinStayLoseShiftPlayer:
    """Wins: keeps the move. Loses: changes to the next in the cycle. Ties: changes to the previous."""
    name = "Win-stay, lose-shift"

    def __init__(self, rng):
        self.rng = rng

    def move(self, history):
        if not history:
            return self.rng.choice(CHOICES)
        player, ai = history[-1]
        outcome = outcome_for_player(player, ai)
        shift = {"WIN": 0, "LOSE": 1, "TIE": 2}[outcome]
        return CHOICES[(INDEX[player] + shift) % 3]


class CounterLastAIPlayer:
    """Plays what would have beaten the AI's last move: a player trying to out-think it."""
    name = "Counters AI's last move"

    def __init__(self, rng):
        self.rng = rng

    def move(self, history):
        return self.rng.choice(CHOICES) if not history else COUNTERS[history[-1][1]]


class SwitchingPlayer:
    """Favours rock, then switches to cycling halfway through."""
    name = "Switches habit midway"

    def __init__(self, rng, switch_at=25):
        self.rng = rng
        self.switch_at = switch_at
        self.cycle = CyclePlayer(rng)

    def move(self, history):
        if len(history) < self.switch_at:
            return self.rng.choices(CHOICES, weights=[0.7, 0.15, 0.15])[0]
        return self.cycle.move(history)


PLAYERS = [RandomPlayer, BiasedPlayer, CyclePlayer, RepeatPatternPlayer, WinStayLoseShiftPlayer,
           CounterLastAIPlayer, SwitchingPlayer]


# ---- the first version's AI, kept as a yardstick ---------------------------------------------

class FirstVersionAI:
    """Counts what follows the previous move, never forgets, always plays the counter."""
    name = "First version"

    def __init__(self, rng):
        self.rng = rng
        self.counts = {m: {n: 1 for n in CHOICES} for m in CHOICES}
        self.last = None

    def lock_move(self):
        class Locked:
            pass
        locked = Locked()
        if self.last is None:
            locked.ai_move = self.rng.choice(CHOICES)
            locked.probs = {m: 1 / 3 for m in CHOICES}
        else:
            row = self.counts[self.last]
            guess = max(row, key=lambda m: row[m] + self.rng.uniform(0, 0.1))
            locked.ai_move = COUNTERS[guess]
            total = sum(row.values())
            locked.probs = {m: row[m] / total for m in CHOICES}
        return locked

    def observe(self, player_move, ai_move=None):
        if self.last is not None:
            self.counts[self.last][player_move] += 1
        self.last = player_move


# ---- matches ---------------------------------------------------------------------------------

@dataclass
class Result:
    net_per_round: float     # AI wins minus AI losses, per round (0 = even, 1 = always wins)
    ai_win_rate: float
    player_win_rate: float
    accuracy: float          # how often the AI's most likely guess was the player's actual move
    stderr: float            # standard error of net_per_round


def play_match(engine, player, rounds):
    history, net, wins, losses, correct = [], 0, 0, 0, 0
    for _ in range(rounds):
        prediction = engine.lock_move()
        move = player.move(history)
        ai_move = prediction.ai_move
        guess = max(prediction.probs, key=prediction.probs.get)
        correct += guess == move
        outcome = outcome_for_player(move, ai_move)
        wins += outcome == "LOSE"
        losses += outcome == "WIN"
        net += (outcome == "LOSE") - (outcome == "WIN")
        engine.observe(move, ai_move)
        history.append((move, ai_move))
    return net, wins, losses, correct


def evaluate(make_engine, make_player, rounds=30, games=400, seed=1):
    """Fresh engine and player each game, as for a stream of visitors."""
    rng = random.Random(seed)
    nets, wins, losses, correct = [], 0, 0, 0
    for _ in range(games):
        net, w, l, c = play_match(make_engine(rng), make_player(rng), rounds)
        nets.append(net / rounds)
        wins += w
        losses += l
        correct += c
    total = rounds * games
    return Result(statistics.fmean(nets), wins / total, losses / total, correct / total,
                  statistics.stdev(nets) / math.sqrt(games))


def new_engine(rng):
    return AdaptiveEngine(rng=random.Random(rng.random()))


def old_engine(rng):
    return FirstVersionAI(random.Random(rng.random()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=30, help="rounds per game (a visitor plays maybe 15-30)")
    parser.add_argument("--games", type=int, default=400)
    args = parser.parse_args()

    print(f"{args.games} games of {args.rounds} rounds each. 'net' = AI wins minus AI losses per round.\n")
    print(f"{'Player':<26}{'First version':>16}{'New AI':>16}{'New AI wins':>14}{'guess right':>14}")
    for make_player in PLAYERS:
        old = evaluate(old_engine, make_player, args.rounds, args.games)
        new = evaluate(new_engine, make_player, args.rounds, args.games)
        print(f"{make_player.name:<26}{old.net_per_round:>+10.3f} ±{old.stderr:.3f}"
              f"{new.net_per_round:>+9.3f} ±{new.stderr:.3f}{new.ai_win_rate:>13.0%}{new.accuracy:>14.0%}")
    print("\nA fair match is net 0.000 (the AI wins about a third, loses a third). "
          "Guessing the next move by chance is right 33% of the time.")


if __name__ == "__main__":
    main()
