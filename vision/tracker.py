"""Camera and MediaPipe. Frames from here are only for detection and the player card."""
import cv2
import numpy as np
import mediapipe as mp

import config


class CameraError(RuntimeError):
    pass


class HandTracker:
    def __init__(self):
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=config.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
        )
        self.cap = None
        self.reconnect()

    @property
    def is_open(self):
        return self.cap is not None and self.cap.isOpened()

    def reconnect(self):
        """(Re)open the camera. Returns True if it is working. Safe to call again and again."""
        if self.cap is not None:
            self.cap.release()
        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        return self.is_open

    def read(self):
        """Return the next mirrored frame, or None if the camera is missing or stopped."""
        if not self.is_open:
            return None
        success, frame = self.cap.read()
        return cv2.flip(frame, 1) if success else None

    def find_hand(self, frame):
        """Return 21 normalised (x, y) landmarks, or None if no hand is visible."""
        results = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if not results.multi_hand_landmarks:
            return None
        return [(lm.x, lm.y) for lm in results.multi_hand_landmarks[0].landmark]

    def release(self):
        if self.cap is not None:
            self.cap.release()
        self.hands.close()


def frame_is_blocked(frame, tolerance=8, share=0.90):
    """True if the picture is almost one flat colour: a closed privacy shutter, a covered lens or a dead camera.

    A shutter that draws a small icon on the grey still counts, because nearly every pixel is the same.
    """
    small = cv2.cvtColor(cv2.resize(frame, (64, 36), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    middle = int(np.median(small))
    return float((np.abs(small.astype(np.int16) - middle) <= tolerance).mean()) >= share


class BlockDetector:
    """Says the camera is blocked only after it has looked blocked for a moment, and clears it just as carefully."""

    def __init__(self, frames_to_block=12, frames_to_clear=4):
        self.frames_to_block = frames_to_block
        self.frames_to_clear = frames_to_clear
        self.blocked = False
        self._streak = 0

    def update(self, frame):
        looks_blocked = frame_is_blocked(frame)
        self._streak = self._streak + 1 if looks_blocked == (not self.blocked) else 0
        if self._streak >= (self.frames_to_block if not self.blocked else self.frames_to_clear):
            self.blocked, self._streak = not self.blocked, 0
        return self.blocked
