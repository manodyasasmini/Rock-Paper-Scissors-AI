"""All tunable values for the game, in one place."""
import os

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "players_data.json")

# Camera and window
CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
WINDOW_NAME = "Rock Paper Scissors AI - Arena"

# Hand detection
MIN_DETECTION_CONFIDENCE = 0.7
MIN_TRACKING_CONFIDENCE = 0.6

# Rounds
COUNTDOWN_SECONDS = 3.0
MATCH_HISTORY_LENGTH = 6
NAME_MAX_LENGTH = 14

# Gesture smoothing: the move is the most common gesture over the last few frames
GESTURE_WINDOW = 10
GESTURE_MIN_VOTES = 6

# Hand skeleton colours (BGR, since the camera picture is drawn with OpenCV)
VIEW_PLAYER = (255, 229, 0)    # #00E5FF
VIEW_NODE = (255, 255, 255)
