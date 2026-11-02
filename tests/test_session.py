import json
import random

import pytest

from ai.engine import MarkovEngine, Prediction
from game.session import (ACTION_QUIT, ACTION_TOGGLE_FULLSCREEN, KEY_BACKSPACE, KEY_ENTER, KEY_ESC,
                          KEY_SPACE, STATE_COUNTDOWN, STATE_IDLE, STATE_NAME_INPUT, STATE_SESSION_CHOICE,
                          STATE_SHOW_RESULT, STATE_SUMMARY, GameSession, determine_winner)
from game.store import PlayerStore


@pytest.fixture
def store(tmp_path):
    return PlayerStore(str(tmp_path / "players.json"))


@pytest.fixture
def session(store):
    return GameSession(store, MarkovEngine(rng=random.Random(3)))


def type_name(session, text):
    for ch in text:
        session.handle_key(ord(ch), 0)


def fix_ai_move(session, move):
    """Make the AI always throw `move`, so results are predictable."""
    uniform = {m: 1 / 3 for m in ("ROCK", "PAPER", "SCISSORS")}
    session.engine.lock_move = lambda: Prediction(uniform, "LOW", "Random", move)


def play_round(session, move, now=0.0):
    session.start_round(now)
    session.update(now + session.countdown_duration, move)


@pytest.mark.parametrize("player,ai,expected", [
    ("ROCK", "SCISSORS", "PLAYER"), ("PAPER", "ROCK", "PLAYER"), ("SCISSORS", "PAPER", "PLAYER"),
    ("ROCK", "PAPER", "AI"), ("PAPER", "SCISSORS", "AI"), ("SCISSORS", "ROCK", "AI"),
    ("ROCK", "ROCK", "TIE"), (None, "ROCK", "INVALID"),
])
def test_determine_winner(player, ai, expected):
    assert determine_winner(player, ai) == expected


def test_new_name_goes_straight_to_the_game_and_is_saved(session, store):
    type_name(session, "Ana")
    session.handle_key(KEY_ENTER, 0)
    assert session.state == STATE_IDLE
    assert "Ana" in store.load_all()


def test_name_input_edits_and_limits_length(session):
    type_name(session, "ab")
    session.handle_key(KEY_BACKSPACE, 0)
    assert session.input_text == "a"
    type_name(session, "x" * 30)
    assert len(session.input_text) == 14


def test_escape_uses_guest(session):
    session.handle_key(KEY_ESC, 0)
    assert session.state == STATE_IDLE
    assert session.player_name == "Guest"


def test_nothing_is_saved_before_a_player_is_chosen(session, store):
    session.save()
    assert store.load_all() == {}


def test_returning_player_chooses_resume_or_new(session, store):
    store.save_player("Ana", {"score_player": 4, "score_ai": 2, "score_ties": 1, "best_streak": 3, "transitions": {}})
    type_name(session, "Ana")
    session.handle_key(KEY_ENTER, 0)
    assert session.state == STATE_SESSION_CHOICE
    assert session.prev_score_player == 4

    session.handle_key(ord("c"), 0)
    assert (session.score_player, session.score_ai, session.score_ties) == (4, 2, 1)

    session.handle_key(ord("p"), 0)
    assert session.state == STATE_NAME_INPUT
    session.handle_key(KEY_ENTER, 0)
    session.handle_key(ord("n"), 0)
    assert (session.score_player, session.score_ai, session.score_ties) == (0, 0, 0)
    assert session.best_streak == 3  # the record is kept


def test_round_waits_for_the_countdown(session):
    session.handle_key(KEY_ESC, 0)
    session.handle_key(KEY_SPACE, 10.0)
    assert session.state == STATE_COUNTDOWN
    session.update(11.0, "ROCK")
    assert session.state == STATE_COUNTDOWN
    session.update(13.0, "ROCK")
    assert session.state == STATE_SHOW_RESULT


def test_ai_move_is_locked_before_the_player_throws(session):
    session.handle_key(KEY_ESC, 0)
    session.start_round(0.0)
    locked = session.prediction.ai_move
    session.update(session.countdown_duration, "PAPER")
    assert session.ai_move == locked


def test_scores_and_streaks(session):
    session.handle_key(KEY_ESC, 0)
    fix_ai_move(session, "SCISSORS")
    play_round(session, "ROCK")
    play_round(session, "ROCK")
    assert (session.score_player, session.streak, session.best_streak) == (2, 2, 2)
    play_round(session, "PAPER")
    assert (session.score_ai, session.streak, session.best_streak) == (1, 0, 2)
    play_round(session, "SCISSORS")
    assert session.score_ties == 1
    assert list(session.match_history) == ["W", "W", "L", "D"]


def test_no_gesture_scores_nothing_and_teaches_nothing(session):
    session.handle_key(KEY_ESC, 0)
    play_round(session, None)
    assert session.round_result == "INVALID"
    assert (session.score_player, session.score_ai, session.score_ties) == (0, 0, 0)
    assert session.engine.last_move is None


def test_progress_is_saved_after_each_round(session, store):
    type_name(session, "Ana")
    session.handle_key(KEY_ENTER, 0)
    fix_ai_move(session, "SCISSORS")
    play_round(session, "ROCK")
    saved = store.load_all()["Ana"]
    assert saved["score_player"] == 1
    assert saved["engine"]["version"] == 2
    assert "transitions" in saved      # the first version's format stays readable by rps_game.py


def test_guests_leave_nothing_behind(session, store):
    session.handle_key(KEY_ESC, 0)
    play_round(session, "ROCK")
    play_round(session, "PAPER")
    session.save()
    assert store.load_all() == {}


def test_the_next_guest_starts_with_a_blank_ai(session):
    session.handle_key(KEY_ESC, 0)
    play_round(session, "ROCK")
    assert session.engine.rounds_seen == 1
    session.handle_key(ord("p"), 0)
    session.handle_key(KEY_ESC, 0)
    assert session.engine.rounds_seen == 0


def test_a_returning_player_keeps_what_the_ai_learned(store):
    first = GameSession(store, MarkovEngine(rng=random.Random(3)))
    type_name(first, "Ana")
    first.handle_key(KEY_ENTER, 0)
    for move in ["ROCK", "PAPER", "ROCK", "PAPER"]:
        play_round(first, move)

    second = GameSession(store, MarkovEngine(rng=random.Random(3)))
    type_name(second, "Ana")
    second.handle_key(KEY_ENTER, 0)
    second.handle_key(ord("c"), 0)
    assert second.engine.rounds_seen == 4
    assert second.engine.last_move is None


def test_reset_clears_scores_but_not_the_ais_memory(session):
    session.handle_key(KEY_ESC, 0)
    play_round(session, "ROCK")
    play_round(session, "PAPER")
    session.handle_key(ord("r"), 0)
    assert (session.score_player, session.score_ai, session.score_ties) == (0, 0, 0)
    assert session.engine.rounds_seen == 2


def test_window_keys_are_returned_as_actions(session):
    session.handle_key(KEY_ESC, 0)
    assert session.handle_key(ord("f"), 0) == ACTION_TOGGLE_FULLSCREEN
    assert session.handle_key(ord("q"), 0) == ACTION_QUIT


def test_corrupt_save_is_kept_not_destroyed(tmp_path):
    path = tmp_path / "players.json"
    path.write_text("{ not json")
    store = PlayerStore(str(path))
    assert store.load_all() == {}
    assert any(p.name.startswith("players.json.corrupt-") for p in tmp_path.iterdir())
    store.save_player("Ana", {"score_player": 1})
    assert json.loads(path.read_text())["Ana"]["score_player"] == 1


def short_match(monkeypatch, rounds=3):
    monkeypatch.setattr("config.MATCH_ROUNDS", rounds)


def test_a_match_ends_after_the_set_number_of_rounds(session, monkeypatch):
    short_match(monkeypatch)
    session.handle_key(KEY_ESC, 0)
    play_round(session, "ROCK")
    play_round(session, "PAPER")
    assert not session.match_complete
    play_round(session, "ROCK")
    assert session.match_complete and session.state == STATE_SHOW_RESULT


def test_space_after_the_last_round_shows_the_summary_then_starts_a_new_match(session, monkeypatch):
    short_match(monkeypatch)
    session.handle_key(KEY_ESC, 0)
    for move in ("ROCK", "PAPER", "ROCK"):
        play_round(session, move)
    scores = (session.score_player, session.score_ai, session.score_ties)

    session.handle_key(KEY_SPACE, 0)
    assert session.state == STATE_SUMMARY
    assert session.summary.rounds == 3
    assert not session.tracking_active            # the camera is not needed on this screen

    session.handle_key(KEY_SPACE, 0)
    assert session.state == STATE_IDLE
    assert session.match_log == [] and session.summary is None
    assert (session.score_player, session.score_ai, session.score_ties) == scores  # running totals carry on


def test_rounds_without_a_detected_hand_do_not_count_toward_the_match(session, monkeypatch):
    short_match(monkeypatch)
    session.handle_key(KEY_ESC, 0)
    play_round(session, None)
    play_round(session, "ROCK")
    assert len(session.match_log) == 1


def test_a_match_length_of_zero_never_ends(session, monkeypatch):
    short_match(monkeypatch, rounds=0)
    session.handle_key(KEY_ESC, 0)
    for _ in range(20):
        play_round(session, "ROCK")
    assert not session.match_complete
    session.handle_key(KEY_SPACE, 0)
    assert session.state == STATE_COUNTDOWN


def test_each_round_gets_an_explanation(session):
    session.handle_key(KEY_ESC, 0)
    play_round(session, "ROCK")
    assert "First throw" in session.explanation
    play_round(session, "ROCK")
    assert session.explanation.startswith("The AI expected")
    play_round(session, None)
    assert "No hand" in session.explanation


def test_switching_player_starts_a_clean_match(session, monkeypatch):
    short_match(monkeypatch)
    session.handle_key(KEY_ESC, 0)
    play_round(session, "ROCK")
    session.handle_key(ord("p"), 0)
    session.handle_key(KEY_ESC, 0)
    assert session.match_log == []


def test_learn_mode_is_off_by_default_and_h_toggles_it(session):
    assert session.learn_mode is False
    session.handle_key(KEY_ESC, 0)
    session.handle_key(ord("h"), 0)
    assert session.learn_mode is True
    session.handle_key(ord("H"), 0)
    assert session.learn_mode is False


def test_h_is_just_a_letter_on_the_name_screen(session):
    session.handle_key(ord("h"), 0)
    assert session.input_text == "h"
    assert session.learn_mode is False


def test_the_explanation_is_still_kept_while_learn_mode_is_off(session):
    session.handle_key(KEY_ESC, 0)
    play_round(session, "ROCK")
    play_round(session, "ROCK")
    assert session.explanation.startswith("The AI expected")
