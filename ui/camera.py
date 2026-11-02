"""The live camera picture for the player's card, with the hand skeleton drawn on top."""
from dataclasses import dataclass

import cv2
import numpy as np

import config
from vision.gesture import HAND_CONNECTIONS


@dataclass
class CameraView:
    image: np.ndarray    # BGR, exactly the requested size
    hand_found: bool


def render_camera(frame, landmarks, out_w, out_h):
    """Fit the camera frame to the panel and draw the skeleton at panel resolution.

    A frame with a different shape than the panel is cropped around its centre, never stretched.
    """
    frame_h, frame_w = frame.shape[:2]
    crop_w = min(frame_w, round(frame_h * out_w / out_h))
    crop_h = min(frame_h, round(frame_w * out_h / out_w))
    x0 = (frame_w - crop_w) // 2
    y0 = (frame_h - crop_h) // 2
    image = cv2.resize(frame[y0:y0 + crop_h, x0:x0 + crop_w], (out_w, out_h), interpolation=cv2.INTER_AREA)

    if landmarks is not None:
        points = [(int(round((x * frame_w - x0) * out_w / crop_w)), int(round((y * frame_h - y0) * out_h / crop_h)))
                  for x, y in landmarks]
        _draw_skeleton(image, points)
    return CameraView(image, landmarks is not None)


def _draw_skeleton(image, points):
    # The glow is soft anyway, so blur it at half size and scale it back up
    h, w = image.shape[:2]
    glow = np.zeros((h // 2, w // 2, 3), dtype=np.uint8)
    for a, b in HAND_CONNECTIONS:
        cv2.line(glow, (points[a][0] // 2, points[a][1] // 2), (points[b][0] // 2, points[b][1] // 2),
                 config.VIEW_PLAYER, 4, cv2.LINE_AA)
    glow = cv2.resize(cv2.GaussianBlur(glow, (0, 0), 3), (w, h), interpolation=cv2.INTER_LINEAR)
    cv2.add(image, glow, dst=image)

    for a, b in HAND_CONNECTIONS:
        cv2.line(image, points[a], points[b], config.VIEW_PLAYER, 2, cv2.LINE_AA)
    for point in points:
        cv2.circle(image, point, 5, config.VIEW_PLAYER, -1, cv2.LINE_AA)
        cv2.circle(image, point, 2, config.VIEW_NODE, -1, cv2.LINE_AA)
