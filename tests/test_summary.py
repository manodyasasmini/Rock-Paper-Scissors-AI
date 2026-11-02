from game.summary import RoundRecord, find_habit, summarize


def record(player, ai="SCISSORS", result="TIE", expected=None, prob=0.0):
    return RoundRecord(player, ai, result, expected, prob)


def test_counts_and_headline():
    records = [record("ROCK", result="PLAYER"), record("ROCK", result="PLAYER"),
               record("PAPER", result="AI"), record("PAPER", result="TIE")]
    summary = summarize(records)
    assert (summary.rounds, summary.wins, summary.losses, summary.ties) == (4, 2, 1, 1)
    assert summary.headline == "YOU WIN"
    assert summarize([record("ROCK", result="AI")]).headline == "AI WINS"
    assert summarize([record("ROCK", result="TIE")]).headline == "DRAW"
    assert summarize([]).headline == "DRAW"


def test_accuracy_only_counts_rounds_where_the_ai_had_a_prediction():
    records = [record("ROCK"),                                   # AI was guessing: not counted
               record("ROCK", expected="ROCK", prob=0.5),        # hit
               record("PAPER", expected="ROCK", prob=0.6),       # miss
               record("PAPER", expected="PAPER", prob=0.7)]      # hit
    summary = summarize(records)
    assert summary.predicted_rounds == 3
    assert summary.hits == 2
    assert abs(summary.accuracy - 2 / 3) < 1e-9
    assert summary.hit_flags == [True, False, True]
    assert summary.running_accuracy == [1.0, 0.5, 2 / 3]


def test_no_predictions_means_zero_accuracy_not_a_crash():
    summary = summarize([record("ROCK"), record("PAPER")])
    assert summary.predicted_rounds == 0
    assert summary.accuracy == 0.0
    assert summary.running_accuracy == []


def moves(*names):
    return [record(name) for name in names]


def test_finds_what_follows_a_move():
    habit = find_habit(moves("ROCK", "PAPER", "ROCK", "PAPER", "ROCK", "PAPER", "ROCK", "PAPER"))
    assert habit == "After ROCK you threw PAPER 4 of 4 times."


def test_needs_three_examples_and_a_clear_majority():
    # After ROCK: PAPER twice only, so too few examples to call it a habit
    assert find_habit(moves("ROCK", "PAPER", "ROCK", "PAPER")) == "The AI found no strong habit: you were hard to read."
    # Every move is followed by at most two examples, and no move is thrown more than a third of the time
    assert "hard to read" in find_habit(moves("ROCK", "PAPER", "SCISSORS", "ROCK", "SCISSORS", "PAPER"))


def test_falls_back_to_a_favourite_move():
    # No move reliably follows another, but rock dominates
    habit = find_habit(moves("ROCK", "ROCK", "PAPER", "ROCK", "SCISSORS", "ROCK", "ROCK", "PAPER", "ROCK", "SCISSORS"))
    assert "ROCK" in habit


def test_the_strongest_habit_wins():
    sequence = ["ROCK", "PAPER"] * 3 + ["SCISSORS", "ROCK", "SCISSORS", "PAPER", "SCISSORS", "ROCK"]
    habit = find_habit(moves(*sequence))
    assert habit.startswith("After ")


def test_an_empty_match_has_no_habit():
    assert "hard to read" in find_habit([])
