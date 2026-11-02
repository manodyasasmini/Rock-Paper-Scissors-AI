"""The live camera picture for the player's card, with the hand skeleton drawn on top."""
from dataclasses import dataclass

import cv2
import numpy as np

import config
from vision.gesture import HAND_CONNECTIONS

HALO = (255, 255, 255)
GRID_BACKGROUND = (251, 240, 234)   # BGR of a pale blue-grey
GRID_LINE = (240, 221, 211)


@dataclass
class CameraView:
    image: np.ndarray    # BGR, exactly the requested size
    hand_found: bool


def render_camera(frame, landmarks, out_w, out_h, skeleton_only=False):
    """Fit the camera frame to the panel and draw the skeleton at panel resolution.

    A frame with a different shape than the panel is cropped around its centre, never stretched.
    With `skeleton_only` the picture is replaced by a plain grid, so faces never appear on screen.
    """
    frame_h, frame_w = frame.shape[:2]
    crop_w = min(frame_w, round(frame_h * out_w / out_h))
    crop_h = min(frame_h, round(frame_w * out_h / out_w))
    x0 = (frame_w - crop_w) // 2
    y0 = (frame_h - crop_h) // 2
    if skeleton_only:
        image = _grid(out_w, out_h)
    else:
        image = cv2.resize(frame[y0:y0 + crop_h, x0:x0 + crop_w], (out_w, out_h), interpolation=cv2.INTER_AREA)

    if landmarks is not None:
        points = [(int(round((x * frame_w - x0) * out_w / crop_w)), int(round((y * frame_h - y0) * out_h / crop_h)))
                  for x, y in landmarks]
        _draw_skeleton(image, points)
    return CameraView(image, landmarks is not None)


def _grid(w, h):
    image = np.empty((h, w, 3), dtype=np.uint8)
    image[:] = GRID_BACKGROUND
    step = max(16, w // 14)
    image[::step, :] = GRID_LINE
    image[:, ::step] = GRID_LINE
    return image


def _draw_skeleton(image, points):
    """A teal skeleton over a white halo, so it shows up against any room."""
    k = image.shape[1] / 408
    halo, bone, radius = max(3, round(9 * k)), max(2, round(3.6 * k)), max(3, round(5.4 * k))
    for a, b in HAND_CONNECTIONS:
        cv2.line(image, points[a], points[b], HALO, halo, cv2.LINE_AA)
    for a, b in HAND_CONNECTIONS:
        cv2.line(image, points[a], points[b], config.VIEW_PLAYER, bone, cv2.LINE_AA)
    for point in points:
        cv2.circle(image, point, radius, config.VIEW_PLAYER, -1, cv2.LINE_AA)
        cv2.circle(image, point, max(1, radius - round(2.4 * k)), config.VIEW_NODE, -1, cv2.LINE_AA)
