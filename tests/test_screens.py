import random

import numpy as np
import pytest

from ai.engine import MarkovEngine
from game.session import (KEY_CTRL_A, KEY_ENTER, KEY_SPACE, STATE_CAMERA_CHECK, STATE_IDLE, STATE_NAME_INPUT,
                          STATE_SHOW_RESULT, STATE_SUMMARY, GameSession)
from game.settings import Settings
from game.store import PlayerStore
from tests.helpers import make_hand
from ui.camera import render_camera
from ui.gestures import ICON_DIR, gesture_icon
from ui.screens import camera_size, render_camera_problem, render_ui

SIZES = [(1280, 720), (1366, 768), (1920, 1080)]


@pytest.fixture
def store(tmp_path):
    store = PlayerStore(str(tmp_path / "p.json"))
    for i, name in enumerate(["Alex", "Sami", "Jo", "Nima"]):
        store.save_player(name, {"best_match": {"wins": 11 - i, "losses": 3 + i, "ties": 1, "fav": "ROCK"}})
    return store


@pytest.fixture
def session(store):
    return GameSession(store, MarkovEngine(rng=random.Random(1)), Settings())


def view_for(state, w, h, hand=True):
    frame = np.full((h, w, 3), 80, dtype=np.uint8)
    return render_camera(frame, make_hand() if hand else None, *camera_size(state, w, h))


def join(session, name="Ana"):
    session.handle_key(KEY_SPACE, 0)
    for ch in name:
        session.handle_key(ord(ch), 0)
    session.handle_key(KEY_ENTER, 0)


def play(session, move, now):
    session.start_round(now)
    session.update(now + 3.0, move)


@pytest.mark.parametrize("w,h", SIZES)
def test_every_screen_renders_at_the_frame_size(session, w, h):
    images = [render_ui(session, w, h, 0.0, None, None)]                           # start
    session.handle_key(KEY_SPACE, 0)
    images.append(render_ui(session, w, h, 0.0, None, None))                       # name
    for ch in "Ana":
        session.handle_key(ord(ch), 0)
    session.handle_key(KEY_ENTER, 0)
    images.append(render_ui(session, w, h, 0.0, "PAPER", view_for(STATE_CAMERA_CHECK, w, h)))   # camera check
    session.start_round(10.0)
    view = view_for(session.state, w, h)
    images.append(render_ui(session, w, h, 11.0, "ROCK", view))                    # countdown
    session.update(13.0, "ROCK")
    images.append(render_ui(session, w, h, 13.0, "ROCK", view))                    # result
    play(session, None, 20.0)
    images.append(render_ui(session, w, h, 23.0, None, view_for(session.state, w, h, hand=False)))  # missed round
    session.handle_key(KEY_CTRL_A, 24.0)
    images.append(render_ui(session, w, h, 24.0, None, view))                      # admin
    session.handle_key(KEY_CTRL_A, 24.0)
    images.append(render_ui(session, w, h, 24.0 + session.settings.idle_seconds + 2, None, view))  # still there?
    images.append(render_camera_problem(w, h, 1.0, 2.0))
    for image in images:
        assert image.shape == (h, w, 3)
    assert not np.array_equal(images[3], images[4])


@pytest.mark.parametrize("w,h", [(1280, 720), (1920, 1080)])
def test_report_and_every_round_render(session, w, h):
    session.settings.match_rounds = 6
    join(session)
    pattern = ["ROCK", "ROCK", "PAPER"]
    for i in range(6):
        play(session, pattern[i % 3], 10.0 * i)
    session.handle_key(KEY_SPACE, 61.0)
    assert session.state == STATE_SUMMARY
    report = render_ui(session, w, h, 62.0, None, None)
    session.handle_key(ord("r"), 62.0)
    replay = render_ui(session, w, h, 63.0, None, None)
    assert report.shape == replay.shape == (h, w, 3)
    assert not np.array_equal(report, replay)


def test_a_report_with_too_few_rounds_still_renders(session):
    session.settings.match_rounds = 2
    join(session)
    play(session, "ROCK", 0.0)
    play(session, "PAPER", 10.0)
    session.handle_key(KEY_SPACE, 20.0)
    assert render_ui(session, 1280, 720, 21.0, None, None).shape == (720, 1280, 3)


def test_an_empty_leaderboard_renders(tmp_path):
    empty = GameSession(PlayerStore(str(tmp_path / "none.json")), MarkovEngine(rng=random.Random(1)), Settings())
    assert render_ui(empty, 1280, 720, 0.0, None, None).shape == (720, 1280, 3)


def test_the_leaderboard_names_appear_on_the_start_screen(session, store):
    with_players = render_ui(session, 1280, 720, 0.0, None, None)
    for name in ("Alex", "Sami", "Jo", "Nima"):
        store.save_player(name, {"best_match": None})
    session.refresh_leaderboard()
    without = render_ui(session, 1280, 720, 0.0, None, None)
    assert not np.array_equal(with_players, without)


def test_a_long_unlimited_or_twenty_round_match_renders(session):
    session.settings.match_rounds = 20
    join(session)
    for i in range(20):
        play(session, "ROCK", 10.0 * i)
    assert render_ui(session, 1280, 720, 300.0, "ROCK", view_for(session.state, 1280, 720)).shape == (720, 1280, 3)
    session.handle_key(KEY_SPACE, 300.0)
    session.handle_key(ord("r"), 300.0)
    assert render_ui(session, 1280, 720, 301.0, None, None).shape == (720, 1280, 3)
    session.settings.match_rounds = 0
    session.handle_key(KEY_SPACE, 302.0)
    session.handle_key(KEY_SPACE, 302.0)
    assert render_ui(session, 1280, 720, 303.0, "ROCK", view_for(session.state, 1280, 720)).shape == (720, 1280, 3)


def test_the_check_screen_uses_a_bigger_camera_picture_than_the_match(session):
    check = camera_size(STATE_CAMERA_CHECK, 1280, 720)
    match = camera_size(STATE_IDLE, 1280, 720)
    assert check == (640, 440) and match == (408, 382)
    assert camera_size(STATE_IDLE, 1920, 1080) == (612, 573)


def test_the_hold_ring_fills_while_a_hand_is_held(session):
    join(session)
    view = view_for(STATE_CAMERA_CHECK, 1280, 720)
    session.update(10.0, "PAPER")
    early = render_ui(session, 1280, 720, 10.1, "PAPER", view)
    session.update(11.5, "PAPER")
    later = render_ui(session, 1280, 720, 11.5, "PAPER", view)
    assert not np.array_equal(early, later)


def test_the_result_screen_shows_the_ais_hand(session):
    join(session)
    session.start_round(10.0)
    view = view_for(session.state, 1280, 720)
    before = render_ui(session, 1280, 720, 12.0, "ROCK", view)
    session.update(13.0, "ROCK")
    assert session.state == STATE_SHOW_RESULT
    after = render_ui(session, 1280, 720, 13.5, "ROCK", view)
    ai_panel = (slice(86, 468), slice(828, 1236))
    assert not np.array_equal(before[ai_panel], after[ai_panel])


def set_expectation(session, probs):
    session.prediction.probs = probs
    session.prediction.expected = max(probs, key=probs.get)


ROCKY = {"ROCK": 0.9, "PAPER": 0.05, "SCISSORS": 0.05}
PAPERY = {"ROCK": 0.1, "PAPER": 0.8, "SCISSORS": 0.1}


def midway(session):
    """Five rounds played, a sixth counting down."""
    join(session)
    for i in range(5):
        play(session, "ROCK", 10.0 * i)
    session.start_round(100.0)
    return slice(482, 622), slice(828, 1236)   # where the AI's tiles, or its learn panel, are drawn


def test_by_default_the_ais_expectation_is_never_drawn(session):
    """Showing it would tell the player which habit to break."""
    view = view_for(STATE_IDLE, 1280, 720)
    area = midway(session)
    assert session.learn_mode is False
    for moment in (101.0, None):
        if moment is None:
            session.update(103.2, "ROCK")
            moment = 104.0
        set_expectation(session, PAPERY)
        first = render_ui(session, 1280, 720, moment, "ROCK", view)[area]
        set_expectation(session, ROCKY)
        assert np.array_equal(first, render_ui(session, 1280, 720, moment, "ROCK", view)[area])


def test_learn_mode_shows_the_expectation_only_after_the_reveal(session):
    view = view_for(STATE_IDLE, 1280, 720)
    area = midway(session)
    session.handle_key(ord("h"), 100.5)
    assert session.learn_mode is True

    set_expectation(session, PAPERY)
    during = render_ui(session, 1280, 720, 101.0, "ROCK", view)[area]
    set_expectation(session, ROCKY)
    assert np.array_equal(during, render_ui(session, 1280, 720, 101.0, "ROCK", view)[area])   # hidden while playing

    session.update(103.2, "ROCK")
    set_expectation(session, PAPERY)
    revealed = render_ui(session, 1280, 720, 104.0, "ROCK", view)[area]
    set_expectation(session, ROCKY)
    assert not np.array_equal(revealed, render_ui(session, 1280, 720, 104.0, "ROCK", view)[area])


def test_skeleton_only_replaces_the_camera_picture_but_keeps_the_hand():
    frame = np.full((720, 1280, 3), 80, dtype=np.uint8)
    frame[:, :] = (30, 60, 200)
    normal = render_camera(frame, make_hand(), 408, 382).image
    private = render_camera(frame, make_hand(), 408, 382, skeleton_only=True).image
    assert private.shape == normal.shape
    assert (normal[5, 5] == (30, 60, 200)).all()
    assert not (private[5, 5] == (30, 60, 200)).all()
    assert (private != private[5, 5]).any()


def test_missing_artwork_falls_back_to_text(session, monkeypatch):
    monkeypatch.setattr("ui.gestures.ICON_DIR", "/no/such/folder")
    monkeypatch.setattr("ui.gestures._sources", {})
    monkeypatch.setattr("ui.gestures._sized", {})
    monkeypatch.setattr("ui.screens._static", {})
    monkeypatch.setattr("ui.screens._hand_cards", {})
    assert gesture_icon("ROCK", 100) is None
    assert render_ui(session, 1280, 720, 0.0, None, None).shape == (720, 1280, 3)
    join(session)
    session.start_round(0.0)
    session.update(3.0, "ROCK")
    assert render_ui(session, 1280, 720, 3.0, "ROCK", view_for(session.state, 1280, 720)).shape == (720, 1280, 3)


@pytest.mark.parametrize("move", ["ROCK", "PAPER", "SCISSORS"])
def test_icons_exist_and_scale(move):
    assert ICON_DIR
    icon = gesture_icon(move, 120)
    assert icon is not None and icon.height == 120 and icon.mode == "RGBA"
    dim = gesture_icon(move, 120, opacity=0.3)
    assert np.array(dim)[:, :, 3].max() <= 0.31 * 255
    flipped = gesture_icon(move, 120, upside_down=True)
    assert flipped.size == icon.size


def test_the_name_screen_shows_what_is_typed(session):
    session.handle_key(KEY_SPACE, 0)
    assert session.state == STATE_NAME_INPUT
    empty = render_ui(session, 1280, 720, 0.0, None, None)
    session.handle_key(ord("A"), 0)
    typed = render_ui(session, 1280, 720, 0.0, None, None)
    assert not np.array_equal(empty, typed)
