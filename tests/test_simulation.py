"""The plan's pass criteria for the AI: fair against random play, strong against real patterns."""
import pytest

from ai import simulate as sim

ROUNDS = 30
GAMES = 200


def run(engine, player, seed=11):
    return sim.evaluate(engine, player, rounds=ROUNDS, games=GAMES, seed=seed)


def test_against_a_random_player_the_match_is_fair():
    result = run(sim.new_engine, sim.RandomPlayer)
    assert abs(result.net_per_round) < 0.06
    assert 0.28 < result.accuracy < 0.38      # guessing a random move is right about a third of the time


@pytest.mark.parametrize("player", [sim.CyclePlayer, sim.RepeatPatternPlayer,
                                    sim.WinStayLoseShiftPlayer, sim.CounterLastAIPlayer])
def test_patterns_are_found_within_a_visit(player):
    result = run(sim.new_engine, player)
    assert result.net_per_round > 0.5
    assert result.accuracy > 0.6


@pytest.mark.parametrize("player", [sim.RepeatPatternPlayer, sim.WinStayLoseShiftPlayer, sim.CounterLastAIPlayer])
def test_clearly_better_than_the_first_version_on_patterns_it_missed(player):
    new = run(sim.new_engine, player)
    old = run(sim.old_engine, player)
    assert new.net_per_round > old.net_per_round + 0.2


def test_a_simple_bias_is_still_exploited():
    assert run(sim.new_engine, sim.BiasedPlayer).net_per_round > 0.15


def test_recovers_after_the_player_changes_habit():
    assert run(sim.new_engine, sim.SwitchingPlayer).net_per_round > 0.2
