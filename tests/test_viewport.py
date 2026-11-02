import numpy as np
import pytest

import config
from tests.helpers import FRAME_H, FRAME_W, make_hand
from vision.viewport import (HINT_EDGE_LEFT, HINT_TOO_CLOSE, HINT_TOO_FAR, STATUS_HOLDING, STATUS_LOST,
                             STATUS_TRACKING, CropController, HandViewport)


def to_pixels(landmarks):
    return [(x * FRAME_W, y * FRAME_H) for x, y in landmarks]


def target(landmarks, aspect=1.0):
    return CropController().target(to_pixels(landmarks), FRAME_W, FRAME_H, aspect)


def test_zoom_does_not_change_between_gestures():
    sizes = [target(make_hand(gesture=g))[2] for g in ("ROCK", "PAPER", "SCISSORS")]
    assert max(sizes) - min(sizes) < 1e-6


def test_zoom_follows_palm_size_but_is_limited():
    near = target(make_hand(palm=200))[2]
    far = target(make_hand(palm=100))[2]
    assert near > far
    assert target(make_hand(palm=20))[2] == pytest.approx(FRAME_H / config.CROP_MAX_ZOOM)
    assert target(make_hand(palm=400))[2] == FRAME_H


def test_first_update_snaps_to_the_hand():
    controller = CropController()
    tx, ty, th = controller.target(to_pixels(make_hand()), FRAME_W, FRAME_H, 1.0)
    assert controller.update(to_pixels(make_hand()), FRAME_W, FRAME_H, 1.0, 0.0) == (tx, ty, th)


def test_crop_follows_a_moving_hand_smoothly():
    controller = CropController()
    controller.update(to_pixels(make_hand(cx=500)), FRAME_W, FRAME_H, 1.0, 0.0)
    moved = to_pixels(make_hand(cx=700))
    goal = controller.target(moved, FRAME_W, FRAME_H, 1.0)[0]

    first = controller.update(moved, FRAME_W, FRAME_H, 1.0, 0.016)[0]
    assert 500 < first < goal  # moved, but not all the way in one frame

    now = 0.016
    for _ in range(120):
        now += 0.016
        cx = controller.update(moved, FRAME_W, FRAME_H, 1.0, now)[0]
    assert abs(cx - goal) <= config.CROP_POSITION_DEADZONE * FRAME_H + 1


def test_tiny_movements_are_ignored():
    controller = CropController()
    start = controller.update(to_pixels(make_hand(cx=640)), FRAME_W, FRAME_H, 1.0, 0.0)[0]
    nudged = controller.update(to_pixels(make_hand(cx=645)), FRAME_W, FRAME_H, 1.0, 0.1)[0]
    assert nudged == start


def test_a_long_gap_snaps_instead_of_sliding():
    controller = CropController()
    controller.update(to_pixels(make_hand(cx=300)), FRAME_W, FRAME_H, 1.0, 0.0)
    hand = to_pixels(make_hand(cx=900))
    goal = controller.target(hand, FRAME_W, FRAME_H, 1.0)[0]
    assert controller.update(hand, FRAME_W, FRAME_H, 1.0, 5.0)[0] == goal


def test_hints():
    assert HandViewport._hints(to_pixels(make_hand(palm=40)), FRAME_W, FRAME_H) == [HINT_TOO_FAR]
    assert HINT_TOO_CLOSE in HandViewport._hints(to_pixels(make_hand(palm=330)), FRAME_W, FRAME_H)
    assert HINT_EDGE_LEFT in HandViewport._hints(to_pixels(make_hand(cx=60)), FRAME_W, FRAME_H)
    assert HandViewport._hints(to_pixels(make_hand()), FRAME_W, FRAME_H) == []


def bright_frame():
    # Stands in for a face and room: loud, varied and nothing like the dark background
    rng = np.random.default_rng(0)
    return rng.integers(120, 255, (FRAME_H, FRAME_W, 3), dtype=np.uint8)


def test_nothing_outside_the_hand_is_shown():
    viewport = HandViewport()
    size = 400
    result = viewport.update(bright_frame(), make_hand(), 0.0, size, size)
    background = viewport.background(size, size)

    assert result.status == STATUS_TRACKING
    assert result.image.shape == (size, size, 3)
    for rows, cols in ((slice(0, 40), slice(0, 40)), (slice(0, 40), slice(size - 40, size)),
                       (slice(size - 40, size), slice(0, 40)), (slice(size - 40, size), slice(size - 40, size))):
        assert np.array_equal(result.image[rows, cols], background[rows, cols])
    assert not np.array_equal(result.image[150:250, 150:250], background[150:250, 150:250])


def test_hand_is_visible_in_the_viewport():
    viewport = HandViewport()
    frame = np.full((FRAME_H, FRAME_W, 3), (60, 140, 200), dtype=np.uint8)
    image = viewport.update(frame, make_hand(), 0.0, 400, 400).image
    palm = image[200:240, 180:220].reshape(-1, 3).mean(axis=0)
    # Camera colour (BGR 60, 140, 200) shows inside the hand, mixed with skeleton lines
    assert palm[2] > palm[0]


def test_losing_the_hand_holds_then_fades_then_clears():
    viewport = HandViewport()
    viewport.update(bright_frame(), make_hand(), 0.0, 300, 300)
    held = viewport.update(bright_frame(), None, config.LOST_HOLD_SECONDS - 0.1, 300, 300)
    assert held.status == STATUS_HOLDING
    assert held.hand_pos is None

    fading = viewport.update(bright_frame(), None, config.LOST_HOLD_SECONDS + 0.1, 300, 300)
    assert fading.status == STATUS_HOLDING

    gone = viewport.update(bright_frame(), None, config.LOST_HOLD_SECONDS + config.LOST_FADE_SECONDS + 0.1, 300, 300)
    assert gone.status == STATUS_LOST
    assert np.array_equal(gone.image, viewport.background(300, 300))


def test_never_shows_the_full_camera_frame_when_no_hand_was_seen():
    viewport = HandViewport()
    result = viewport.update(bright_frame(), None, 0.0, 300, 300)
    assert result.status == STATUS_LOST
    assert np.array_equal(result.image, viewport.background(300, 300))


def test_hand_near_the_frame_edge_still_renders_at_full_size():
    viewport = HandViewport()
    result = viewport.update(bright_frame(), make_hand(cx=30, cy=40), 0.0, 320, 320)
    assert result.image.shape == (320, 320, 3)
