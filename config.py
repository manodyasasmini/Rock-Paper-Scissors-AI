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

# Crop controller: zoom comes from palm size, which barely changes between gestures
CROP_PALM_SCALE = 3.6          # crop height as a multiple of palm size
CROP_BBOX_MARGIN = 1.25        # widen if the hand's bounding box would not fit otherwise
CROP_MAX_ZOOM = 2.5            # a distant hand is not enlarged beyond this
CROP_POSITION_TAU = 0.08       # seconds; lower follows the hand faster
CROP_ZOOM_IN_TAU = 0.6
CROP_ZOOM_OUT_TAU = 0.25       # zooming out is faster, so fingers are not cut off for long
CROP_POSITION_DEADZONE = 0.02  # fraction of crop height
CROP_ZOOM_DEADZONE = 0.06      # fraction of crop height

# Hand mask, as fractions of palm size in the viewport
MASK_FINGER_THICKNESS = 0.42
MASK_FEATHER = 0.05

# When tracking is lost: hold the last image, then fade to the placeholder
LOST_HOLD_SECONDS = 0.5
LOST_FADE_SECONDS = 0.3

# Placement guidance
HINT_TOO_FAR_PALM = 0.10       # palm size as a fraction of frame height
HINT_TOO_CLOSE_PALM = 0.42
HINT_EDGE_MARGIN = 0.03        # fraction of the frame

# Viewport colours (BGR, since the viewport is drawn with OpenCV)
VIEW_BG = (20, 11, 7)          # #070B14
VIEW_GRID = (34, 22, 16)
VIEW_PLAYER = (255, 229, 0)    # #00E5FF
VIEW_PLAYER_DIM = (128, 92, 0)
VIEW_NODE = (255, 255, 255)
VIEW_WARN = (32, 176, 255)     # #FFB020
VIEW_MUTED = (181, 155, 138)   # #8A9BB5
