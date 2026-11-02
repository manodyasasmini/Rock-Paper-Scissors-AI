"""Camera and MediaPipe. Frames from here are only for detection and the player card."""
import cv2
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
