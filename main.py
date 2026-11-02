"""Rock Paper Scissors AI Battle Arena: the redesigned version."""
import sys
import time

import cv2

import config
from game.session import ACTION_QUIT, ACTION_TOGGLE_FULLSCREEN, GameSession
from game.store import PlayerStore
from ui.camera import render_camera
from ui.screens import camera_size, render_ui
from vision.gesture import GestureSmoother, detect_gesture
from vision.tracker import CameraError, HandTracker

NO_KEY = 255


def main():
    try:
        tracker = HandTracker()
    except CameraError as error:
        print(f"ERROR: {error}")
        return 1

    session = GameSession(PlayerStore(config.DATA_FILE))
    smoother = GestureSmoother()

    cv2.namedWindow(config.WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    is_fullscreen = True

    print("==========================================")
    print("  Rock Paper Scissors AI Battle Arena!    ")
    print("  Type your name and press [ENTER]        ")
    print("  [SPACE] Play Round                      ")
    print("  [P]     Switch Player Profile           ")
    print("  [F]     Toggle Fullscreen               ")
    print("  [D]     Toggle AI difficulty            ")
    print("  [R]     Reset Score                     ")
    print("  [Q]     Quit                            ")
    print("==========================================")

    try:
        while True:
            frame = tracker.read()
            if frame is None:
                print("ERROR: The camera stopped sending frames.")
                break
            now = time.time()
            height, width = frame.shape[:2]

            live_gesture = None
            view = None
            if session.tracking_active:
                landmarks = tracker.find_hand(frame)
                raw_gesture = detect_gesture(landmarks) if landmarks else None
                live_gesture = smoother.update(raw_gesture)
                view = render_camera(frame, landmarks, *camera_size(width, height))
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
