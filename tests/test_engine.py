import json
import random

import pytest

import config

from ai.engine import (CHOICES, COUNTERS, EXPERT_FREQUENCY, EXPERT_LAST_TWO, MODE_RANDOM, AdaptiveEngine,
                       explain, outcome_for_player)


def make_engine(seed=1):
    return AdaptiveEngine(rng=random.Random(seed))


def feed(engine, moves, ai_move="SCISSORS"):
    for move in moves:
        engine.observe(move, ai_move)


def test_first_round_has_no_history_and_is_low_evidence():
    prediction = make_engine().lock_move()
    assert prediction.ai_move in CHOICES
    assert prediction.evidence == "LOW"
    assert prediction.top_expert == "No history yet"
    assert abs(sum(prediction.probs.values()) - 1) < 1e-9


def test_probabilities_always_sum_to_one():
    engine = make_engine()
    rng = random.Random(5)
    for _ in range(40):
        engine.observe(rng.choice(CHOICES), rng.choice(CHOICES))
        probs = engine.lock_move().probs
        assert abs(sum(probs.values()) - 1) < 1e-9
        assert all(0 <= p <= 1 for p in probs.values())


def test_learns_what_follows_a_move_and_counters_it():
    engine = make_engine()
    feed(engine, ["ROCK", "PAPER"] * 10 + ["ROCK"])  # after ROCK, this player always throws PAPER
    prediction = engine.lock_move()
    assert max(prediction.probs, key=prediction.probs.get) == "PAPER"

    counter = COUNTERS["PAPER"]
    played = 0
    for seed in range(200):
        engine.rng = random.Random(seed)
        played += engine.lock_move().ai_move == counter
    assert played >= 170  # a clear pattern is exploited almost every time


def test_two_observations_are_not_trusted_much():
    engine = make_engine()
    feed(engine, ["ROCK", "PAPER"])
    assert max(engine.lock_move().probs.values()) < 0.6


def test_evidence_grows_with_observations():
    engine = make_engine()
    feed(engine, ["ROCK"])
    assert engine.lock_move().evidence == "LOW"
    feed(engine, ["PAPER", "ROCK"] * 20)
    assert engine.lock_move().evidence == "HIGH"


def test_old_habits_fade():
    engine = make_engine()
    feed(engine, ["ROCK"] * 40)
    feed(engine, ["PAPER"] * 25)
    probs = engine.lock_move().probs
    assert probs["PAPER"] > probs["ROCK"]


def test_second_order_pattern_is_found_when_one_move_is_ambiguous():
    # After ROCK the next move is ROCK or PAPER (50/50), but after ROCK, ROCK it is always PAPER
    engine = make_engine()
    feed(engine, ["ROCK", "ROCK", "PAPER"] * 12 + ["ROCK", "ROCK"])
    prediction = engine.lock_move()
    assert prediction.probs["PAPER"] > 0.7
    assert prediction.top_expert == EXPERT_LAST_TWO


def test_a_move_that_was_not_detected_teaches_nothing():
    engine = make_engine()
    feed(engine, ["ROCK", "PAPER"])
    before = (engine.rounds_seen, engine.last_move, engine.to_dict())
    engine.observe(None, "ROCK")
    assert (engine.rounds_seen, engine.last_move, engine.to_dict()) == before


def test_random_mode_ignores_history():
    engine = make_engine()
    engine.toggle_mode()
    assert engine.mode == MODE_RANDOM
    feed(engine, ["ROCK"] * 20)
    prediction = engine.lock_move()
    assert prediction.top_expert == "Random"
    assert set(prediction.probs.values()) == {1 / 3}


@pytest.mark.parametrize("player,ai,expected", [
    ("ROCK", "SCISSORS", "WIN"), ("ROCK", "PAPER", "LOSE"), ("PAPER", "PAPER", "TIE"),
])
def test_outcome_for_player(player, ai, expected):
    assert outcome_for_player(player, ai) == expected


def test_memory_survives_saving_and_loading():
    engine = make_engine()
    rng = random.Random(9)
    for _ in range(25):
        engine.observe(rng.choice(CHOICES), rng.choice(CHOICES))
    saved = json.loads(json.dumps(engine.to_dict()))  # must survive being written as JSON

    restored = make_engine()
    restored.load_record({"engine": saved})
    assert restored.to_dict() == engine.to_dict()
    assert restored.last_move is None  # a new session has no previous move
    assert restored.rounds_seen == 25


def test_returning_player_is_predicted_from_habits_on_the_first_move():
    engine = make_engine()
    feed(engine, ["ROCK"] * 12)
    restored = make_engine()
    restored.load_record({"engine": engine.to_dict()})
    prediction = restored.lock_move()
    assert prediction.top_expert == EXPERT_FREQUENCY
    assert prediction.probs["ROCK"] > 0.6


def test_first_versions_save_is_understood():
    engine = make_engine()
    engine.load_record({"transitions": {"ROCK": {"ROCK": 1, "PAPER": 6, "SCISSORS": 1}}})
    assert engine.m1[0, 1] == 5          # the old format started every count at 1
    assert engine.rounds_seen == 5


def test_legacy_format_is_written_for_the_old_game():
    engine = make_engine()
    feed(engine, ["ROCK", "PAPER", "ROCK", "PAPER"])
    legacy = engine.legacy_transitions()
    assert legacy["ROCK"] == {"ROCK": 1, "PAPER": 3, "SCISSORS": 1} or legacy["ROCK"]["PAPER"] >= 2
    assert all(isinstance(v, int) and v >= 1 for row in legacy.values() for v in row.values())


def test_damaged_memory_falls_back_instead_of_crashing():
    engine = make_engine()
    engine.load_record({"engine": {"version": 2, "freq": [1, 2]},
                        "transitions": {"ROCK": {"ROCK": 1, "PAPER": 4, "SCISSORS": 1}}})
    assert engine.m1[0, 1] == 3
    engine.load_record({"engine": "garbage"})
    assert engine.rounds_seen == 0
    assert engine.lock_move().ai_move in CHOICES


def test_reset_forgets_everything():
    engine = make_engine()
    feed(engine, ["ROCK"] * 10)
    engine.reset()
    assert engine.rounds_seen == 0
    assert engine.lock_move().top_expert == "No history yet"


def pattern_engine():
    engine = make_engine()
    feed(engine, ["ROCK", "ROCK", "PAPER"] * 12 + ["ROCK", "ROCK"])
    return engine


def test_prediction_says_what_it_expects_and_why():
    prediction = pattern_engine().lock_move()
    assert prediction.expected == "PAPER"
    assert prediction.reason == "you often throw paper after rock then rock"


def test_explanation_when_the_ai_was_right():
    prediction = pattern_engine().lock_move()
    sentence = explain(prediction, "PAPER")
    assert sentence.startswith("The AI expected PAPER (")
    assert "because you often throw paper after rock then rock" in sentence
    assert sentence.endswith("You threw it.")


def test_explanation_when_the_player_broke_the_pattern():
    sentence = explain(pattern_engine().lock_move(), "SCISSORS")
    assert "But you threw SCISSORS." in sentence
    assert "You broke your pattern!" in sentence


def test_a_missed_guess_with_little_evidence_is_not_called_a_broken_pattern():
    engine = make_engine()
    feed(engine, ["ROCK", "ROCK"])
    prediction = engine.lock_move()
    assert prediction.evidence == "LOW"
    sentence = explain(prediction, "SCISSORS" if prediction.expected != "SCISSORS" else "ROCK")
    assert "broke your pattern" not in sentence
    assert "an early guess" in sentence


def test_explanations_for_special_cases():
    assert "No hand" in explain(pattern_engine().lock_move(), None)
    assert "First throw" in explain(make_engine().lock_move(), "ROCK")
    random_engine = make_engine()
    random_engine.toggle_mode()
    assert explain(random_engine.lock_move(), "ROCK") == "Random mode: the AI just guessed."


def test_a_guess_has_no_expected_move():
    prediction = make_engine().lock_move()
    assert prediction.expected is None and prediction.reason == ""


def test_with_no_standout_move_the_ai_only_guesses_and_says_so():
    """Expecting PAPER at 34% against 33% each would be a coin toss: don't claim a prediction."""
    engine = make_engine()
    prediction = engine.lock_move()
    prediction.top_expert, prediction.expected = "Frequency", None
    assert "No move stood out" in explain(prediction, "PAPER")

    feed(engine, ["ROCK", "PAPER", "SCISSORS", "ROCK", "PAPER", "SCISSORS"])
    flat = engine.lock_move()
    top, second = sorted(flat.probs.values(), reverse=True)[:2]
    assert (top - second < config.AI_CLEAR_MARGIN) == (flat.expected is None)


def test_a_clear_expectation_also_says_what_the_ai_played():
    sentence = explain(pattern_engine().lock_move(), "ROCK")
    assert "so it played" in sentence
