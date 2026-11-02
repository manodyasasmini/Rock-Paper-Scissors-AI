import random

from ai.engine import CHOICES, COUNTERS, MODE_RANDOM, MarkovEngine


def make_engine(seed=1):
    return MarkovEngine(rng=random.Random(seed))


def test_first_round_has_no_history_and_is_low_evidence():
    prediction = make_engine().lock_move()
    assert prediction.ai_move in CHOICES
    assert prediction.evidence == "LOW"
    assert abs(sum(prediction.probs.values()) - 1) < 1e-9


def test_counters_the_most_likely_next_move():
    engine = make_engine()
    for _ in range(8):  # player always follows ROCK with PAPER
        engine.observe("ROCK")
        engine.observe("PAPER")
    engine.observe("ROCK")
    prediction = engine.lock_move()
    assert prediction.ai_move == COUNTERS["PAPER"]
    assert prediction.probs["PAPER"] > 0.6


def test_evidence_grows_with_observations():
    engine = make_engine()
    levels = set()
    for i in range(40):  # evidence counts the row for the last move, so each row needs 15+ moves
        engine.observe("ROCK" if i % 2 else "PAPER")
        levels.add(engine.lock_move().evidence)
    assert {"LOW", "HIGH"} <= levels


def test_no_move_detected_teaches_nothing():
    engine = make_engine()
    engine.observe("ROCK")
    engine.observe(None)
    assert engine.last_move == "ROCK"
    assert engine.to_dict() == {}


def test_random_mode_ignores_history():
    engine = make_engine()
    engine.toggle_mode()
    assert engine.mode == MODE_RANDOM
    for _ in range(10):
        engine.observe("ROCK")
    assert engine.lock_move().top_expert == "Random"


def test_save_and_load_round_trip():
    engine = make_engine()
    for move in ["ROCK", "PAPER", "ROCK", "SCISSORS", "ROCK"]:
        engine.observe(move)
    restored = make_engine()
    restored.load(engine.to_dict())
    assert restored.to_dict() == engine.to_dict()
    assert restored.last_move is None  # a new session has no previous move


def test_loading_old_saves_missing_a_move_still_works():
    engine = make_engine()
    engine.load({"ROCK": {"ROCK": 4}})
    engine.observe("ROCK")
    assert engine.lock_move().probs["ROCK"] > 0.5
