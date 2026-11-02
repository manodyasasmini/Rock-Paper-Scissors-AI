import cv2
import numpy as np

from tests.helpers import FRAME_H, FRAME_W
from vision.tracker import BlockDetector, frame_is_blocked


def shutter_frame():
    """The grey picture a closed privacy shutter produces, with its small padlock icon."""
    frame = np.full((FRAME_H, FRAME_W, 3), 138, dtype=np.uint8)
    cv2.rectangle(frame, (500, 260), (780, 460), (240, 240, 240), 6)       # a big icon, larger than the real one
    cv2.circle(frame, (640, 360), 40, (240, 240, 240), 6)
    return frame


def room_frame(seed=0):
    rng = np.random.default_rng(seed)
    base = cv2.resize(rng.integers(40, 220, (9, 16, 3), dtype=np.uint8), (FRAME_W, FRAME_H), interpolation=cv2.INTER_CUBIC)
    return np.clip(base.astype(np.int16) + rng.normal(0, 4, base.shape), 0, 255).astype(np.uint8)


def test_a_closed_shutter_and_a_covered_lens_count_as_blocked():
    assert frame_is_blocked(shutter_frame())
    assert frame_is_blocked(np.zeros((FRAME_H, FRAME_W, 3), np.uint8))
    assert frame_is_blocked(np.random.default_rng(1).normal(12, 2, (FRAME_H, FRAME_W, 3)).clip(0, 255).astype(np.uint8))


def test_a_real_scene_is_not_blocked():
    assert not frame_is_blocked(room_frame())
    gradient = np.tile(np.linspace(60, 200, FRAME_W, dtype=np.uint8), (FRAME_H, 1))[:, :, None].repeat(3, axis=2)
    assert not frame_is_blocked(gradient)


def test_blocked_is_announced_only_after_it_persists_and_cleared_quickly():
    detector = BlockDetector(frames_to_block=5, frames_to_clear=2)
    for _ in range(4):
        assert not detector.update(shutter_frame())      # a short blank moment is ignored
    assert detector.update(shutter_frame())
    assert detector.update(room_frame())                 # one good frame is not enough
    assert not detector.update(room_frame())
    for _ in range(3):
        detector.update(shutter_frame())
    assert not detector.update(room_frame())             # blips never switch it on


def test_the_camera_check_screen_says_when_the_camera_is_blocked():
    import random
    import tempfile, os
    from ai.engine import MarkovEngine
    from game.session import KEY_ENTER, KEY_SPACE, GameSession
    from game.settings import Settings
    from game.store import PlayerStore
    from ui.screens import render_ui

    session = GameSession(PlayerStore(os.path.join(tempfile.mkdtemp(), "p.json")), MarkovEngine(rng=random.Random(1)), Settings())
    session.handle_key(KEY_SPACE, 0)
    session.handle_key(KEY_ENTER, 0)
    normal = render_ui(session, 1280, 720, 0.0, None, None)
    session.camera_blocked = True
    blocked = render_ui(session, 1280, 720, 0.0, None, None)
    assert not np.array_equal(normal, blocked)


def test_a_blocked_camera_is_named_in_the_middle_of_a_match_too():
    import os, random, tempfile
    from ai.engine import MarkovEngine
    from game.session import KEY_ENTER, KEY_SPACE, GameSession
    from game.settings import Settings
    from game.store import PlayerStore
    from ui.screens import render_ui

    session = GameSession(PlayerStore(os.path.join(tempfile.mkdtemp(), "p.json")), MarkovEngine(rng=random.Random(1)), Settings())
    session.handle_key(KEY_SPACE, 0)
    session.handle_key(KEY_ENTER, 0)
    session.handle_key(KEY_SPACE, 0)          # camera check skipped: the first round starts
    session.update(session.countdown_duration, None)   # nothing seen: a missed round
    plain_miss = render_ui(session, 1280, 720, 5.0, None, None)
    session.camera_blocked = True
    blocked_miss = render_ui(session, 1280, 720, 5.0, None, None)
    chip_and_message = (slice(95, 130), slice(380, 460)), (slice(300, 560), slice(520, 760))
    for rows, cols in chip_and_message:
        assert not np.array_equal(plain_miss[rows, cols], blocked_miss[rows, cols])
