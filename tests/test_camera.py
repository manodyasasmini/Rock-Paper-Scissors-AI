import numpy as np

from tests.helpers import FRAME_H, FRAME_W, make_hand
from ui.camera import render_camera


def plain_frame(value=90):
    return np.full((FRAME_H, FRAME_W, 3), value, dtype=np.uint8)


def test_output_is_exactly_the_requested_size():
    view = render_camera(plain_frame(), None, 560, 315)
    assert view.image.shape == (315, 560, 3)
    assert not view.hand_found


def test_without_a_hand_the_picture_is_just_the_camera():
    view = render_camera(plain_frame(90), None, 560, 315)
    assert (view.image == 90).all()


def test_a_hand_gets_a_skeleton_drawn_over_the_picture():
    view = render_camera(plain_frame(90), make_hand(), 560, 315)
    assert view.hand_found
    assert (view.image != 90).any()


def test_a_different_shape_is_cropped_not_stretched():
    # Left half red, right half blue. A square panel keeps the middle strip, so both colours stay
    frame = plain_frame()
    frame[:, : FRAME_W // 2] = (0, 0, 200)
    frame[:, FRAME_W // 2:] = (200, 0, 0)
    image = render_camera(frame, None, 300, 300).image
    assert image[150, 5][2] > 150 and image[150, 295][0] > 150
    # A square cut from a 16:9 frame shows 720 of its 1280 columns, so each colour fills half the panel
    assert abs(int((image[150, :, 2] > 150).sum()) - 150) <= 2


def test_skeleton_follows_the_crop():
    # Hand at the exact centre of the frame must land at the centre of any panel size
    landmarks = make_hand(cx=FRAME_W / 2, cy=FRAME_H / 2, palm=100)
    for size in ((560, 315), (300, 300)):
        image = render_camera(plain_frame(90), landmarks, *size).image
        marked = np.argwhere((image != 90).any(axis=2))
        centre_x = (marked[:, 1].min() + marked[:, 1].max()) / 2
        assert abs(centre_x - size[0] / 2) < size[0] * 0.15
