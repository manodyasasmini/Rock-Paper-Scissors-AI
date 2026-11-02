"""Rock Paper Scissors AI: a webcam game against an AI that learns your habits."""
import sys
import time

import cv2

import config
from game.session import ACTION_QUIT, ACTION_TOGGLE_FULLSCREEN, GameSession
from game.settings import Settings
from game.store import PlayerStore
from ui.camera import render_camera
from ui.screens import camera_size, render_camera_problem, render_ui
from vision.gesture import GestureSmoother, detect_gesture
from vision.tracker import HandTracker

NO_KEY = 255
CAMERA_RETRY_SECONDS = 3.0


def main():
    tracker = HandTracker()
    settings = Settings(config.SETTINGS_FILE)
    session = GameSession(PlayerStore(config.DATA_FILE), settings=settings)
    smoother = GestureSmoother()

    cv2.namedWindow(config.WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    is_fullscreen = True
    size = (config.CAMERA_WIDTH, config.CAMERA_HEIGHT)
    next_retry = 0.0

    print("==========================================")
    print("  Rock Paper Scissors AI                  ")
    print("  [SPACE] Play      [Q] Quit              ")
    print("  [F] Fullscreen    [Ctrl+A] Admin        ")
    print("==========================================")

    try:
        while True:
            now = time.time()
            frame = tracker.read()
            if frame is None:
                # The camera is missing or stopped: say so, and keep trying by itself
                if now >= next_retry:
                    tracker.reconnect()
                    next_retry = now + CAMERA_RETRY_SECONDS
                cv2.imshow(config.WINDOW_NAME, render_camera_problem(*size, now, next_retry - now))
                key = cv2.waitKey(30) & 0xFF
                if key in (ord("q"), ord("Q")) or cv2.getWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
                continue
            next_retry = 0.0
            height, width = frame.shape[:2]
            size = (width, height)

            live_gesture = None
            view = None
            if session.tracking_active:
                landmarks = tracker.find_hand(frame)
                raw_gesture = detect_gesture(landmarks) if landmarks else None
                live_gesture = smoother.update(raw_gesture)
                view = render_camera(frame, landmarks, *camera_size(session.state, width, height),
                                     skeleton_only=settings.skeleton_only)
            else:
                smoother.clear()

            session.update(now, live_gesture)
            cv2.imshow(config.WINDOW_NAME, render_ui(session, width, height, now, live_gesture, view))

            key = cv2.waitKey(1) & 0xFF
            if key != NO_KEY:
                action = session.handle_key(key, now)
                if action == ACTION_QUIT:
                    break
                if action == ACTION_TOGGLE_FULLSCREEN:
                    is_fullscreen = not is_fullscreen
                    mode = cv2.WINDOW_FULLSCREEN if is_fullscreen else cv2.WINDOW_NORMAL
                    cv2.setWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, mode)

            # Closing the window with the mouse also quits
            if cv2.getWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        session.save()
        tracker.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
