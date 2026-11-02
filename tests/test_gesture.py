import pytest

from tests.helpers import make_hand, rotate
from vision.gesture import GestureSmoother, detect_gesture


@pytest.mark.parametrize("gesture", ["ROCK", "PAPER", "SCISSORS"])
def test_detects_each_gesture(gesture):
    assert detect_gesture(make_hand(gesture=gesture)) == gesture


@pytest.mark.parametrize("turns", [1, 2, 3])
def test_detection_does_not_depend_on_hand_rotation(turns):
    # Rotating a square-pixel hand about the centre keeps the shape, so the answer must not change.
    # The helper hand is built in a 1280x720 frame, so use a square frame for this check.
    hand = make_hand(cx=360, cy=360, gesture="SCISSORS", frame_w=720, frame_h=720)
    assert detect_gesture(rotate(hand, turns)) == "SCISSORS"


def test_three_fingers_is_not_a_move():
    hand = make_hand(gesture="PAPER")
    hand[20] = hand[18]  # fold the little finger tip back to its middle knuckle
    hand[16] = hand[14]
    hand[12] = hand[10]
    assert detect_gesture(hand) in ("ROCK", None)


def test_smoother_needs_enough_matching_frames():
    smoother = GestureSmoother(window=10, min_votes=6)
    results = [smoother.update("ROCK") for _ in range(6)]
    assert results[:5] == [None] * 5
    assert results[5] == "ROCK"


def test_smoother_ignores_a_flicker():
    smoother = GestureSmoother(window=10, min_votes=6)
    for _ in range(8):
        smoother.update("PAPER")
    assert smoother.update(None) == "PAPER"
    assert smoother.update("ROCK") == "PAPER"


def test_smoother_clear_forgets():
    smoother = GestureSmoother(window=10, min_votes=3)
    for _ in range(5):
        smoother.update("ROCK")
    smoother.clear()
    assert smoother.update("ROCK") is None
