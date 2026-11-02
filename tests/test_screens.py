import random

import numpy as np
import pytest

from ai.engine import MarkovEngine
from game.session import GameSession, KEY_ENTER, KEY_ESC, KEY_SPACE
from game.store import PlayerStore
from tests.helpers import FRAME_H, FRAME_W, make_hand
from ui.camera import render_camera
from ui.gestures import ICON_DIR, gesture_icon
from ui.screens import arena_layout, camera_size, render_ui

SIZES = [(1280, 720), (1366, 768), (1920, 1080)]


@pytest.fixture
def session(tmp_path):
    return GameSession(PlayerStore(str(tmp_path / "p.json")), MarkovEngine(rng=random.Random(1)))


def view_for(w, h):
    frame = np.full((h, w, 3), 80, dtype=np.uint8)
    return render_camera(frame, make_hand(), *camera_size(w, h))


@pytest.mark.parametrize("w,h", SIZES)
def test_layout_fits_the_canvas(w, h):
    lay = arena_layout(w, h)
    assert lay["player_x1"] + lay["card_w"] < lay["ai_x1"]
    assert lay["ai_x1"] + lay["card_w"] <= w
    assert lay["panel_w"] <= lay["card_w"] - 40
    assert lay["strip_y1"] + 80 <= lay["strip_y2"]
    assert lay["strip_y2"] < lay["card_y2"] <= h


@pytest.mark.parametrize("w,h", SIZES)
def test_every_screen_renders_at_the_canvas_size(session, w, h):
    view = view_for(w, h)
    images = [render_ui(session, w, h, 0.0, None, None)]                  # name screen
    session.handle_key(KEY_ESC, 0)
    images.append(render_ui(session, w, h, 0.0, "PAPER", view))           # idle
    session.handle_key(KEY_SPACE, 10.0)
    images.append(render_ui(session, w, h, 11.0, "ROCK", view))           # countdown
    session.update(13.0, "ROCK")
    images.append(render_ui(session, w, h, 13.0, "ROCK", view))           # result
    for image in images:
        assert image.shape == (h, w, 3)
    assert not np.array_equal(images[1], images[3])


def test_result_screen_shows_both_hands(session):
    w, h = 1280, 720
    view = view_for(w, h)
    session.handle_key(KEY_ESC, 0)
    session.handle_key(KEY_SPACE, 10.0)
    session.update(13.0, "ROCK")
    before = render_ui(session, w, h, 9.0, "ROCK", view)
    session.state = "IDLE"
    idle = render_ui(session, w, h, 9.0, "ROCK", view)
    lay = arena_layout(w, h)
    ai_panel = (slice(lay["panel_y1"], lay["panel_y1"] + lay["panel_h"]),
                slice(lay["ai_x1"] + 20, lay["ai_x1"] + 20 + lay["panel_w"]))
    assert not np.array_equal(before[ai_panel], idle[ai_panel])  # the AI's hand appears on reveal


def test_missing_artwork_falls_back_to_text(session, monkeypatch):
    monkeypatch.setattr("ui.gestures.ICON_DIR", "/no/such/folder")
    monkeypatch.setattr("ui.gestures._sources", {})
    monkeypatch.setattr("ui.gestures._sized", {})
    assert gesture_icon("ROCK", 100) is None
    session.handle_key(KEY_ESC, 0)
    assert render_ui(session, 1280, 720, 0.0, "ROCK", view_for(1280, 720)).shape == (720, 1280, 3)


@pytest.mark.parametrize("move", ["ROCK", "PAPER", "SCISSORS"])
def test_icons_exist_and_scale(move):
    assert ICON_DIR
    icon = gesture_icon(move, 120)
    assert icon is not None and icon.height == 120 and icon.mode == "RGBA"
    dim = gesture_icon(move, 120, opacity=0.3)
    assert np.array(dim)[:, :, 3].max() <= 0.31 * 255
    flipped = gesture_icon(move, 120, upside_down=True)
    assert flipped.size == icon.size


@pytest.mark.parametrize("w,h", SIZES)
def test_summary_and_ai_read_screens_render(session, monkeypatch, w, h):
    monkeypatch.setattr("config.MATCH_ROUNDS", 6)
    view = view_for(w, h)
    session.handle_key(KEY_ESC, 0)
    pattern = ["ROCK", "ROCK", "PAPER"]
    for i in range(6):
        session.start_round(10.0 * i)
        session.update(10.0 * i + 3, pattern[i % 3])
        image = render_ui(session, w, h, 10.0 * i + 4, pattern[i % 3], view)
        assert image.shape == (h, w, 3)
    session.handle_key(KEY_SPACE, 100.0)
    assert session.state == "SUMMARY"
    assert render_ui(session, w, h, 101.0, None, None).shape == (h, w, 3)


def test_the_bars_stay_hidden_until_the_reveal(session):
    """Showing the AI's expectation during play would tell the player how to beat it."""
    w, h = 1280, 720
    view = view_for(w, h)
    session.handle_key(KEY_ESC, 0)
    for i in range(5):
        session.start_round(10.0 * i)
        session.update(10.0 * i + 3, "ROCK")
    session.start_round(100.0)
    lay = arena_layout(w, h)
    ai_panel = (slice(lay["panel_y1"], lay["panel_y1"] + lay["panel_h"]),
                slice(lay["ai_x1"] + 20 + 220, lay["ai_x1"] + 20 + lay["panel_w"]))

    during = render_ui(session, w, h, 101.0, "ROCK", view)[ai_panel]
    session.prediction.probs = {"ROCK": 0.9, "PAPER": 0.05, "SCISSORS": 0.05}   # a very different expectation
    session.prediction.expected = "ROCK"
    assert np.array_equal(during, render_ui(session, w, h, 101.0, "ROCK", view)[ai_panel])

    session.update(103.2, "ROCK")
    revealed = render_ui(session, w, h, 104.0, "ROCK", view)[ai_panel]
    assert not np.array_equal(during, revealed)
    session.prediction.probs = {"ROCK": 0.1, "PAPER": 0.8, "SCISSORS": 0.1}     # after the reveal the bars do follow it
    session.prediction.expected = "PAPER"
    assert not np.array_equal(revealed, render_ui(session, w, h, 104.0, "ROCK", view)[ai_panel])
