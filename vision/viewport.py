"""The hand-only viewport: a smoothed crop around the hand, with everything else hidden.

The full camera frame is only used for detection. What the player and any onlookers
see is the hand on a dark background, so faces and rooms never appear on screen.
"""
import math
from dataclasses import dataclass, field

import cv2
import numpy as np

import config
from vision.gesture import HAND_CONNECTIONS

WRIST = 0
MIDDLE_KNUCKLE = 9
PALM_POINTS = [0, 5, 9, 13, 17]
PALM_OUTLINE = [0, 1, 5, 9, 13, 17]

STATUS_TRACKING = "tracking"
STATUS_HOLDING = "holding"   # hand just lost; the last image is kept briefly
STATUS_LOST = "lost"

HINT_TOO_FAR = "TOO_FAR"
HINT_TOO_CLOSE = "TOO_CLOSE"
HINT_EDGE_LEFT = "EDGE_LEFT"
HINT_EDGE_RIGHT = "EDGE_RIGHT"
HINT_EDGE_TOP = "EDGE_TOP"


@dataclass
class ViewResult:
    image: np.ndarray                     # BGR, exactly the requested size
    status: str
    hints: list = field(default_factory=list)
    hand_pos: tuple = None                # palm centre as a fraction of the camera frame


def _approach(current, target, dt, tau):
    return current + (target - current) * (1.0 - math.exp(-dt / tau))


def _approach_with_deadzone(current, target, dt, tau, deadzone):
    """Move toward target but stay put while it is within the dead-zone."""
    error = target - current
    if abs(error) <= deadzone:
        return current
    return _approach(current, target - math.copysign(deadzone, error), dt, tau)


class CropController:
    """Decides where the crop is. Pure maths on pixel coordinates, so it can be tested alone."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.cx = self.cy = self.h = None
        self.last_time = None

    def target(self, points, frame_w, frame_h, aspect):
        pts = np.asarray(points, dtype=np.float64)
        palm = math.dist(pts[WRIST], pts[MIDDLE_KNUCKLE])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        bbox_w, bbox_h = hi - lo

        # Zoom comes from palm size, which hardly changes between rock, paper and scissors.
        # The bounding box only widens the crop if the fingers would not fit.
        crop_h = max(palm * config.CROP_PALM_SCALE, max(bbox_h, bbox_w / aspect) * config.CROP_BBOX_MARGIN)
        crop_h = min(max(crop_h, frame_h / config.CROP_MAX_ZOOM), frame_h)

        palm_centre = pts[PALM_POINTS].mean(axis=0)
        bbox_centre = (lo + hi) / 2
        centre = 0.5 * palm_centre + 0.5 * bbox_centre
        return centre[0], centre[1], crop_h

    def update(self, points, frame_w, frame_h, aspect, now):
        tx, ty, th = self.target(points, frame_w, frame_h, aspect)
        if self.h is None or now - self.last_time > 1.0:
            self.cx, self.cy, self.h = tx, ty, th
        else:
            dt = max(now - self.last_time, 1e-3)
            dead = config.CROP_POSITION_DEADZONE * self.h
            self.cx = _approach_with_deadzone(self.cx, tx, dt, config.CROP_POSITION_TAU, dead)
            self.cy = _approach_with_deadzone(self.cy, ty, dt, config.CROP_POSITION_TAU, dead)
            # A growing crop (zooming out) is faster, so fingers are not cut off for long
            tau = config.CROP_ZOOM_OUT_TAU if th > self.h else config.CROP_ZOOM_IN_TAU
            self.h = _approach_with_deadzone(self.h, th, dt, tau, config.CROP_ZOOM_DEADZONE * self.h)
        self.last_time = now
        return self.cx, self.cy, self.h


def _odd(n):
    n = max(3, int(n))
    return n if n % 2 else n + 1


class HandViewport:
    def __init__(self):
        self.crop = CropController()
        self.last_image = None
        self.last_seen = None
        self._backgrounds = {}

    def reset(self):
        self.crop.reset()
        self.last_image = None
        self.last_seen = None

    def background(self, w, h):
        """Dark grid with corner brackets, shown wherever there is no hand."""
        if (w, h) not in self._backgrounds:
            bg = np.full((h, w, 3), config.VIEW_BG, dtype=np.uint8)
            for gx in range(0, w, 40):
                cv2.line(bg, (gx, 0), (gx, h), config.VIEW_GRID, 1)
            for gy in range(0, h, 40):
                cv2.line(bg, (0, gy), (w, gy), config.VIEW_GRID, 1)
            inset, arm = 12, max(20, min(w, h) // 12)
            for sx, x in ((1, inset), (-1, w - 1 - inset)):
                for sy, y in ((1, inset), (-1, h - 1 - inset)):
                    cv2.line(bg, (x, y), (x + sx * arm, y), config.VIEW_PLAYER_DIM, 2, cv2.LINE_AA)
                    cv2.line(bg, (x, y), (x, y + sy * arm), config.VIEW_PLAYER_DIM, 2, cv2.LINE_AA)
            self._backgrounds[(w, h)] = bg
        return self._backgrounds[(w, h)]

    def update(self, frame, landmarks, now, out_w, out_h):
        if landmarks is None:
            return self._without_hand(now, out_w, out_h)

        frame_h, frame_w = frame.shape[:2]
        points = [(x * frame_w, y * frame_h) for x, y in landmarks]
        cx, cy, crop_h = self.crop.update(points, frame_w, frame_h, out_w / out_h, now)

        # One affine warp crops, zooms and fills anything outside the frame with the background
        scale = out_h / crop_h
        offset_x = out_w / 2 - cx * scale
        offset_y = out_h / 2 - cy * scale
        matrix = np.float32([[scale, 0, offset_x], [0, scale, offset_y]])
        cropped = cv2.warpAffine(frame, matrix, (out_w, out_h), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=config.VIEW_BG)
        out_points = [(int(round(px * scale + offset_x)), int(round(py * scale + offset_y))) for px, py in points]
        palm_out = math.dist(out_points[WRIST], out_points[MIDDLE_KNUCKLE])

        image = self._mask_to_hand(cropped, out_points, palm_out, out_w, out_h)
        self._draw_skeleton(image, out_points)

        self.last_image = image
        self.last_seen = now
        return ViewResult(image, STATUS_TRACKING, self._hints(points, frame_w, frame_h),
                          self._palm_position(points, frame_w, frame_h))

    def _mask_to_hand(self, cropped, out_points, palm_out, w, h):
        thickness = max(4, int(palm_out * config.MASK_FINGER_THICKNESS))
        mask = np.zeros((h, w), dtype=np.uint8)
        for a, b in HAND_CONNECTIONS:
            cv2.line(mask, out_points[a], out_points[b], 255, thickness, cv2.LINE_AA)
        for point in out_points:
            cv2.circle(mask, point, thickness // 2, 255, -1, cv2.LINE_AA)
        outline = np.array([out_points[i] for i in PALM_OUTLINE], dtype=np.int32)
        cv2.fillConvexPoly(mask, cv2.convexHull(outline), 255, cv2.LINE_AA)

        kernel = _odd(palm_out * config.MASK_FEATHER * 2)
        mask = cv2.GaussianBlur(mask, (kernel, kernel), 0)

        # Everything outside the mask is the background, never the camera image.
        # Whole-number maths: several times faster than blending in floating point.
        alpha = cv2.merge([mask, mask, mask])
        hand = cv2.multiply(cropped, alpha, scale=1 / 255.0)
        rest = cv2.multiply(self.background(w, h), 255 - alpha, scale=1 / 255.0)
        return cv2.add(hand, rest)

    @staticmethod
    def _draw_skeleton(image, out_points):
        # The glow is soft anyway, so blur it at half size and scale it back up
        h, w = image.shape[:2]
        glow = np.zeros((h // 2, w // 2, 3), dtype=np.uint8)
        for a, b in HAND_CONNECTIONS:
            cv2.line(glow, (out_points[a][0] // 2, out_points[a][1] // 2),
                     (out_points[b][0] // 2, out_points[b][1] // 2), config.VIEW_PLAYER, 4, cv2.LINE_AA)
        glow = cv2.resize(cv2.GaussianBlur(glow, (0, 0), 3), (w, h), interpolation=cv2.INTER_LINEAR)
        cv2.add(image, glow, dst=image)

        for a, b in HAND_CONNECTIONS:
            cv2.line(image, out_points[a], out_points[b], config.VIEW_PLAYER, 2, cv2.LINE_AA)
        for point in out_points:
            cv2.circle(image, point, 5, config.VIEW_PLAYER, -1, cv2.LINE_AA)
            cv2.circle(image, point, 2, config.VIEW_NODE, -1, cv2.LINE_AA)

    def _without_hand(self, now, w, h):
        background = self.background(w, h)
        if self.last_image is None or self.last_image.shape[:2] != (h, w):
            return ViewResult(background.copy(), STATUS_LOST)

        gone_for = now - self.last_seen
        if gone_for <= config.LOST_HOLD_SECONDS:
            return ViewResult(self.last_image, STATUS_HOLDING)
        fade = (gone_for - config.LOST_HOLD_SECONDS) / config.LOST_FADE_SECONDS
        if fade >= 1.0:
            return ViewResult(background.copy(), STATUS_LOST)
        return ViewResult(cv2.addWeighted(self.last_image, 1.0 - fade, background, fade, 0), STATUS_HOLDING)

    @staticmethod
    def _palm_position(points, frame_w, frame_h):
        centre = np.asarray(points)[PALM_POINTS].mean(axis=0)
        return float(centre[0] / frame_w), float(centre[1] / frame_h)

    @staticmethod
    def _hints(points, frame_w, frame_h):
        hints = []
        palm_fraction = math.dist(points[WRIST], points[MIDDLE_KNUCKLE]) / frame_h
        if palm_fraction < config.HINT_TOO_FAR_PALM:
            hints.append(HINT_TOO_FAR)
        elif palm_fraction > config.HINT_TOO_CLOSE_PALM:
            hints.append(HINT_TOO_CLOSE)

        xs = [x / frame_w for x, _ in points]
        ys = [y / frame_h for _, y in points]
        if min(xs) < config.HINT_EDGE_MARGIN:
            hints.append(HINT_EDGE_LEFT)
        if max(xs) > 1 - config.HINT_EDGE_MARGIN:
            hints.append(HINT_EDGE_RIGHT)
        if min(ys) < config.HINT_EDGE_MARGIN:
            hints.append(HINT_EDGE_TOP)
        return hints
