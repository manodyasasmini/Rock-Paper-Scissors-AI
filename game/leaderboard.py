"""The leaderboard: each named player's best match, ranked by how far they beat the AI. Pure data."""
from collections import Counter

import config


def match_score_key(best):
    """Higher is better: biggest winning margin first, then most wins."""
    return (best["wins"] - best["losses"], best["wins"])


def result_of(match_log):
    """Wins, losses, and favourite move of a finished match."""
    moves = Counter(r.player_move for r in match_log)
    return {
        "wins": sum(r.result == "PLAYER" for r in match_log),
        "losses": sum(r.result == "AI" for r in match_log),
        "ties": sum(r.result == "TIE" for r in match_log),
        "fav": moves.most_common(1)[0][0] if moves else "ROCK",
    }


def ranking(profiles):
    """[(name, best_match)] best first, for profiles that have finished a match."""
    entries = [(name, p["best_match"]) for name, p in profiles.items() if p.get("best_match")]
    entries.sort(key=lambda item: (match_score_key(item[1]), item[0]), reverse=True)
    return entries


def top(profiles, size=config.LEADERBOARD_SIZE):
    return ranking(profiles)[:size]


def rank_of(profiles, name):
    """1-based rank of a player, or None if they have no finished match."""
    for i, (entry_name, _) in enumerate(ranking(profiles)):
        if entry_name == name:
            return i + 1
    return None
