import json
import random

import pytest

import config
from ai.engine import MarkovEngine, Prediction
from game.session import (ACTION_QUIT, ACTION_TOGGLE_FULLSCREEN, KEY_BACKSPACE, KEY_CTRL_A, KEY_ENTER, KEY_ESC,
                          KEY_SPACE, STATE_CAMERA_CHECK, STATE_COUNTDOWN, STATE_IDLE, STATE_NAME_INPUT,
                          STATE_REPLAY, STATE_SHOW_RESULT, STATE_START, STATE_SUMMARY, GameSession,
                          determine_winner)
from game.settings import Settings
from game.store import PlayerStore


@pytest.fixture
def store(tmp_path):
    return PlayerStore(str(tmp_path / "players.json"))


@pytest.fixture
def session(store):
    return GameSession(store, MarkovEngine(rng=random.Random(3)), Settings())


def type_name(session, text, now=0.0):
    for ch in text:
        session.handle_key(ord(ch), now)


def begin(session, name="", now=0.0):
    """Walk through the start screen and the name screen. Leaves the session on the camera check."""
    session.handle_key(KEY_SPACE, now)
    type_name(session, name, now)
    session.handle_key(KEY_ENTER, now)
    assert session.state == STATE_CAMERA_CHECK


def fix_ai_move(session, move):
    """Make the AI always throw `move`, so results are predictable."""
    uniform = {m: 1 / 3 for m in ("ROCK", "PAPER", "SCISSORS")}
    session.engine.lock_move = lambda: Prediction(uniform, "LOW", "Random", move)


def play_round(session, move, now=0.0):
    session.start_round(now)
    session.update(now + session.countdown_duration, move)


def finish_match(session, rounds=3, move="ROCK", ai="SCISSORS"):
    session.settings.match_rounds = rounds
    fix_ai_move(session, ai)
    for _ in range(rounds):
        play_round(session, move)
    session.handle_key(KEY_SPACE, 0.0)
    assert session.state == STATE_SUMMARY


@pytest.mark.parametrize("player,ai,expected", [
    ("ROCK", "SCISSORS", "PLAYER"), ("PAPER", "ROCK", "PLAYER"), ("SCISSORS", "PAPER", "PLAYER"),
    ("ROCK", "PAPER", "AI"), ("PAPER", "SCISSORS", "AI"), ("SCISSORS", "ROCK", "AI"),
    ("ROCK", "ROCK", "TIE"), (None, "ROCK", "INVALID"),
])
def test_determine_winner(player, ai, expected):
    assert determine_winner(player, ai) == expected


# ---- getting in: start, name, camera check ----
def test_the_game_opens_on_the_start_screen(session):
    assert session.state == STATE_START
    assert not session.tracking_active


def test_space_leads_to_the_name_then_the_camera_check(session, store):
    session.handle_key(KEY_SPACE, 0)
    assert session.state == STATE_NAME_INPUT
    type_name(session, "Ana")
    session.handle_key(KEY_ENTER, 0)
    assert session.state == STATE_CAMERA_CHECK
    assert session.player_name == "Ana"
    assert "Ana" in store.load_all()
    assert session.tracking_active


def test_name_input_edits_and_limits_length(session):
    session.handle_key(KEY_SPACE, 0)
    type_name(session, "ab")
    session.handle_key(KEY_BACKSPACE, 0)
    assert session.input_text == "a"
    type_name(session, "x" * 30)
    assert len(session.input_text) == config.NAME_MAX_LENGTH


def test_an_empty_name_plays_as_a_guest_and_nothing_is_saved(session, store):
    begin(session)
    assert session.is_guest
    play_round(session, "ROCK")
    session.save()
    assert store.load_all() == {}


def test_a_name_that_differs_only_in_case_is_the_same_player(session, store):
    store.save_player("Ana", {"transitions": {}})
    begin(session, "ana")
    assert session.player_name == "Ana"
    assert list(store.load_all()) == ["Ana"]


def test_guest_typed_by_hand_is_still_a_guest(session):
    begin(session, "GUEST")
    assert session.is_guest


def test_escape_steps_back_one_screen(session):
    begin(session, "Ana")
    session.handle_key(KEY_ESC, 0)
    assert session.state == STATE_NAME_INPUT
    session.handle_key(KEY_ESC, 0)
    assert session.state == STATE_START


def test_nothing_is_saved_before_a_player_is_chosen(session, store):
    session.save()
    assert store.load_all() == {}


def test_holding_a_hand_still_passes_the_check_but_waits_for_space(session):
    begin(session, "Ana")
    session.update(10.0, "PAPER")
    assert session.hold_progress(10.5) == pytest.approx(0.25)
    session.update(10.0 + config.HOLD_TO_START_SECONDS, "PAPER")
    assert session.check_passed and session.state == STATE_CAMERA_CHECK    # the player starts the match
    session.update(30.0, None)
    assert session.check_passed and session.hold_progress(30.0) == 1.0
    session.handle_key(KEY_SPACE, 30.0)
    assert session.state == STATE_COUNTDOWN


def test_losing_the_hand_restarts_the_hold(session):
    begin(session, "Ana")
    session.update(10.0, "PAPER")
    session.update(11.0, None)
    assert session.hold_progress(11.0) == 0
    session.update(11.5, "PAPER")
    session.update(13.0, "PAPER")
    assert session.state == STATE_CAMERA_CHECK


def test_space_skips_the_wait_on_the_camera_check(session):
    begin(session, "Ana")
    session.handle_key(KEY_SPACE, 0)
    assert session.state == STATE_COUNTDOWN


# ---- rounds ----
def test_round_waits_for_the_countdown(session):
    begin(session)
    session.handle_key(KEY_SPACE, 10.0)
    assert session.state == STATE_COUNTDOWN
    session.update(11.0, "ROCK")
    assert session.state == STATE_COUNTDOWN
    session.update(13.0, "ROCK")
    assert session.state == STATE_SHOW_RESULT


def test_ai_move_is_locked_before_the_player_throws(session):
    begin(session)
    session.start_round(0.0)
    locked = session.prediction.ai_move
    session.update(session.countdown_duration, "PAPER")
    assert session.ai_move == locked


def test_scores_and_streaks(session):
    begin(session)
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
    begin(session)
    play_round(session, None)
    assert session.round_result == "INVALID"
    assert (session.score_player, session.score_ai, session.score_ties) == (0, 0, 0)
    assert session.engine.last_move is None
    assert session.match_log == []


def test_the_round_number_counts_rounds_with_a_hand(session):
    begin(session)
    assert session.round_number == 1
    play_round(session, "ROCK")
    assert session.round_number == 1          # the result of round 1 is on screen
    session.handle_key(KEY_SPACE, 0)
    assert session.round_number == 2


def test_each_round_gets_an_explanation(session):
    begin(session)
    play_round(session, "ROCK")
    assert "First throw" in session.explanation
    play_round(session, "ROCK")
    assert session.explanation.startswith("The AI expected")
    play_round(session, None)
    assert "No hand" in session.explanation


# ---- saving ----
def test_progress_is_saved_after_each_round(session, store):
    begin(session, "Ana")
    fix_ai_move(session, "SCISSORS")
    play_round(session, "ROCK")
    saved = store.load_all()["Ana"]
    assert saved["score_player"] == 1
    assert saved["engine"]["version"] == 2
    assert "transitions" in saved      # the first version's format stays readable by rps_game.py


def test_the_next_guest_starts_with_a_blank_ai(session):
    begin(session)
    play_round(session, "ROCK")
    assert session.engine.rounds_seen == 1
    session.handle_key(ord("p"), 0)
    assert session.state == STATE_START
    begin(session)
    assert session.engine.rounds_seen == 0


def test_a_returning_player_keeps_what_the_ai_learned(store):
    first = GameSession(store, MarkovEngine(rng=random.Random(3)), Settings())
    begin(first, "Ana")
    for move in ["ROCK", "PAPER", "ROCK", "PAPER"]:
        play_round(first, move)

    second = GameSession(store, MarkovEngine(rng=random.Random(3)), Settings())
    begin(second, "Ana")
    assert second.engine.rounds_seen == 4
    assert second.engine.last_move is None
    assert second.score_player == second.score_ai == 0     # but the scores belong to the match


def test_window_keys_are_returned_as_actions(session):
    assert session.handle_key(ord("f"), 0) == ACTION_TOGGLE_FULLSCREEN
    assert session.handle_key(ord("q"), 0) == ACTION_QUIT


def test_q_and_f_are_just_letters_on_the_name_screen(session):
    session.handle_key(KEY_SPACE, 0)
    assert session.handle_key(ord("q"), 0) is None
    assert session.handle_key(ord("f"), 0) is None
    assert session.input_text == "qf"


def test_corrupt_save_is_kept_not_destroyed(tmp_path):
    path = tmp_path / "players.json"
    path.write_text("{ not json")
    store = PlayerStore(str(path))
    assert store.load_all() == {}
    assert any(p.name.startswith("players.json.corrupt-") for p in tmp_path.iterdir())
    store.save_player("Ana", {"score_player": 1})
    assert json.loads(path.read_text())["Ana"]["score_player"] == 1


# ---- the match, the report and the leaderboard ----
def test_a_match_ends_after_the_set_number_of_rounds(session):
    session.settings.match_rounds = 3
    begin(session)
    play_round(session, "ROCK")
    play_round(session, "PAPER")
    assert not session.match_complete
    play_round(session, "ROCK")
    assert session.match_complete and session.state == STATE_SHOW_RESULT


def test_space_after_the_last_round_shows_the_report_then_play_again_starts_fresh(session):
    begin(session, "Ana")
    finish_match(session)
    assert session.summary.rounds == 3
    assert not session.tracking_active            # the camera is not needed on this screen

    session.handle_key(KEY_SPACE, 0)
    assert session.state == STATE_IDLE
    assert session.player_name == "Ana"           # same player, straight into the next match
    assert session.match_log == [] and session.summary is None
    assert (session.score_player, session.score_ai, session.score_ties) == (0, 0, 0)


def test_rounds_without_a_detected_hand_do_not_count_toward_the_match(session):
    session.settings.match_rounds = 3
    begin(session)
    play_round(session, None)
    play_round(session, "ROCK")
    assert len(session.match_log) == 1


def test_a_match_length_of_zero_never_ends(session):
    session.settings.match_rounds = 0
    begin(session)
    for _ in range(20):
        play_round(session, "ROCK")
    assert not session.match_complete
    session.handle_key(KEY_SPACE, 0)
    assert session.state == STATE_COUNTDOWN


def test_a_finished_match_goes_on_the_leaderboard(session, store):
    begin(session, "Ana")
    finish_match(session, rounds=3)
    assert store.load_all()["Ana"]["best_match"] == {"wins": 3, "losses": 0, "ties": 0, "fav": "ROCK"}
    assert session.rank == 1


def test_only_a_better_match_replaces_the_best(session, store):
    begin(session, "Ana")
    finish_match(session, rounds=3)
    session.handle_key(KEY_SPACE, 0)
    finish_match(session, rounds=3, move="ROCK", ai="PAPER")        # three losses
    assert store.load_all()["Ana"]["best_match"]["wins"] == 3


def test_guests_never_reach_the_leaderboard(session, store):
    begin(session)
    finish_match(session)
    assert session.rank is None
    assert store.load_all() == {}


def test_the_leaderboard_ranks_by_margin(store):
    store.save_player("Low", {"best_match": {"wins": 5, "losses": 5, "ties": 5, "fav": "ROCK"}})
    store.save_player("High", {"best_match": {"wins": 11, "losses": 3, "ties": 1, "fav": "PAPER"}})
    store.save_player("Mid", {"best_match": {"wins": 9, "losses": 4, "ties": 2, "fav": "ROCK"}})
    store.save_player("Never", {"transitions": {}})
    session = GameSession(store, MarkovEngine(rng=random.Random(3)), Settings())
    assert [name for name, _ in session.leaderboard_rows] == ["High", "Mid", "Low"]


def test_r_shows_every_round_and_space_returns(session):
    begin(session, "Ana")
    finish_match(session)
    session.handle_key(ord("r"), 0)
    assert session.state == STATE_REPLAY
    session.handle_key(KEY_SPACE, 0)
    assert session.state == STATE_SUMMARY


def test_n_returns_to_the_start_screen_with_the_new_score_on_the_board(session):
    begin(session, "Ana")
    finish_match(session)
    session.handle_key(ord("n"), 0)
    assert session.state == STATE_START
    assert session.player_name is None
    assert [name for name, _ in session.leaderboard_rows] == ["Ana"]


def test_p_in_a_match_returns_to_the_start_screen(session):
    begin(session, "Ana")
    play_round(session, "ROCK")
    session.handle_key(ord("p"), 0)
    assert session.state == STATE_START and session.match_log == []


# ---- walking away ----
def test_a_quiet_player_is_asked_then_sent_back_to_the_start(session):
    begin(session, "Ana", now=0.0)
    limit = session.settings.idle_seconds
    session.update(limit - 1, None)
    assert session.idle_remaining(limit - 1) is None
    session.update(limit + 1, None)
    assert session.state == STATE_CAMERA_CHECK and session.idle_remaining(limit + 1) > 0
    session.update(limit + config.IDLE_WARNING_SECONDS + 1, None)
    assert session.state == STATE_START


def test_a_key_answers_still_there_without_doing_anything_else(session):
    begin(session, "Ana", now=0.0)
    late = session.settings.idle_seconds + 2
    assert session.idle_remaining(late) is not None
    session.handle_key(ord("p"), late)
    assert session.state == STATE_CAMERA_CHECK
    assert session.idle_remaining(late + 1) is None


def test_a_hand_in_view_counts_as_being_there(session):
    begin(session, "Ana", now=0.0)
    session.update(session.settings.idle_seconds - 1, "PAPER")
    session.update(session.settings.idle_seconds + 1, None)
    assert session.idle_remaining(session.settings.idle_seconds + 1) is None


def test_nobody_is_timed_out_during_a_countdown_or_on_the_start_screen(session):
    assert session.idle_remaining(10_000) is None
    begin(session, "Ana")
    session.start_round(0.0)
    assert session.idle_remaining(1.0) is None


# ---- operator settings ----
def test_ctrl_a_opens_and_closes_the_admin_panel(session):
    session.handle_key(KEY_CTRL_A, 0)
    assert session.admin_open
    session.handle_key(KEY_ESC, 0)
    assert not session.admin_open


def test_admin_keys_change_settings_and_save_them(store, tmp_path):
    settings = Settings(str(tmp_path / "settings.json"))
    session = GameSession(store, MarkovEngine(rng=random.Random(3)), settings)
    session.handle_key(KEY_CTRL_A, 0)
    session.handle_key(ord("1"), 0)
    assert settings.match_rounds == 20
    session.handle_key(ord("2"), 0)
    assert settings.learn_mode and session.learn_mode
    session.handle_key(ord("3"), 0)
    assert settings.skeleton_only
    session.handle_key(ord("4"), 0)
    assert settings.idle_seconds == 30
    assert Settings(str(tmp_path / "settings.json")).match_rounds == 20   # survives a restart


def test_the_leaderboard_is_cleared_only_after_pressing_five_twice(session, store):
    store.save_player("Ana", {"best_match": {"wins": 5, "losses": 1, "ties": 0, "fav": "ROCK"}})
    session.refresh_leaderboard()
    session.handle_key(KEY_CTRL_A, 0)
    session.handle_key(ord("5"), 0)
    assert store.load_all()["Ana"].get("best_match")
    session.handle_key(ord("5"), 0)
    assert "best_match" not in store.load_all()["Ana"]
    assert session.leaderboard_rows == []


def test_the_game_keys_do_nothing_while_admin_is_open(session):
    session.handle_key(KEY_CTRL_A, 0)
    session.handle_key(KEY_SPACE, 0)
    assert session.state == STATE_START


def test_a_broken_settings_file_falls_back_to_the_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ nope")
    assert Settings(str(path)).match_rounds == config.MATCH_ROUNDS


# ---- learn mode ----
def test_learn_mode_is_off_by_default_and_h_toggles_it(session):
    assert session.learn_mode is False
    begin(session)
    session.start_round(0.0)
    session.update(10.0, "ROCK")
    session.handle_key(ord("h"), 10.0)
    assert session.learn_mode is True
    session.handle_key(ord("H"), 10.0)
    assert session.learn_mode is False


def test_h_is_just_a_letter_on_the_name_screen(session):
    session.handle_key(KEY_SPACE, 0)
    session.handle_key(ord("h"), 0)
    assert session.input_text == "h"
    assert session.learn_mode is False


def test_the_explanation_is_still_kept_while_learn_mode_is_off(session):
    begin(session)
    play_round(session, "ROCK")
    play_round(session, "ROCK")
    assert session.explanation.startswith("The AI expected")


def test_on_the_ready_screen_a_held_hand_does_not_start_the_round(session):
    begin(session, "Ana")
    session.handle_key(KEY_SPACE, 0)
    session.update(3.0, "ROCK")
    session.handle_key(KEY_SPACE, 3.0)
    session.state = STATE_IDLE
    for second in range(10):
        session.update(10.0 + second, "PAPER")
    assert session.state == STATE_IDLE


def test_going_back_to_the_name_resets_the_camera_check(session):
    begin(session, "Ana")
    session.update(1.0, "PAPER")
    session.update(1.0 + config.HOLD_TO_START_SECONDS, "PAPER")
    assert session.check_passed
    session.handle_key(KEY_ESC, 5.0)
    session.handle_key(KEY_ENTER, 5.0)
    assert session.state == STATE_CAMERA_CHECK and not session.check_passed
