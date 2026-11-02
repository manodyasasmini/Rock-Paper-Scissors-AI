"""Turns 21 hand landmarks into a move. Landmarks are (x, y) pairs, normalised 0-1."""
import math
from collections import Counter, deque

import config

WRIST = 0
FINGER_TIPS = [8, 12, 16, 20]
FINGER_PIPS = [6, 10, 14, 18]

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]


def detect_gesture(landmarks):
    wrist_x, wrist_y = landmarks[WRIST]

    def dist_to_wrist(idx):
        return math.hypot(landmarks[idx][0] - wrist_x, landmarks[idx][1] - wrist_y)

    # A finger is extended when its tip is farther from the wrist than its middle
    # knuckle. Unlike comparing y-coordinates, this works at any hand rotation.
    fingers_extended = [
        dist_to_wrist(tip) > dist_to_wrist(pip) * 1.05
        for tip, pip in zip(FINGER_TIPS, FINGER_PIPS)
    ]
    open_count = sum(fingers_extended)

    if open_count == 0:
        return "ROCK"
    if open_count >= 4:
        return "PAPER"
    if fingers_extended[0] and fingers_extended[1] and not fingers_extended[2] and not fingers_extended[3]:
        return "SCISSORS"
    return None


class GestureSmoother:
    def __init__(self, window=config.GESTURE_WINDOW, min_votes=config.GESTURE_MIN_VOTES):
        self.buffer = deque(maxlen=window)
        self.min_votes = min_votes

    def update(self, raw_gesture):
        """Record this frame's gesture and return the stable one (or None if unsure)."""
        self.buffer.append(raw_gesture)
        votes = Counter(g for g in self.buffer if g is not None)
        if not votes:
            return None
        gesture, count = votes.most_common(1)[0]
        return gesture if count >= self.min_votes else None

    def clear(self):
        self.buffer.clear()
