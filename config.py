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
NAME_MAX_LENGTH = 12

# Gesture smoothing: the move is the most common gesture over the last few frames
GESTURE_WINDOW = 10
GESTURE_MIN_VOTES = 6

# Hand skeleton colours (BGR, since the camera picture is drawn with OpenCV)
VIEW_PLAYER = (136, 148, 13)    # teal #0D9488
VIEW_NODE = (255, 255, 255)

# AI engine. Tuned with `python -m ai.simulate` against scripted players; re-tune after real play-tests.
AI_DECAY = 0.95            # each round, old observations count this much less (half-life about 13 rounds)
AI_SMOOTHING = 0.5         # pseudo-count per move; keeps estimates near 1/3 until there is real evidence
AI_SCORE_FORGET = 0.9      # how fast an expert's track record fades
AI_TRUST_SHARPNESS = 3.0   # how strongly the AI favours the better-performing expert
AI_CLEAR_MARGIN = 0.08     # the AI only claims to "expect" a move when it leads the next best by this much
AI_SOFTMAX_K = 12.0         # higher = the AI commits harder to its best move; lower = more random
# Evidence = decayed observations behind the lead prediction. Measured in simulation: accuracy jumps
# from about 53% to 78% at 2 observations and levels off near 80% from about 5.
EVIDENCE_MEDIUM = 2
EVIDENCE_HIGH = 5

# Matches: a visitor plays this many rounds, then sees what the AI learned. 0 = play on without end.
MATCH_ROUNDS = 15

# Learn mode shows what the AI expected after every round. Off by default, because it tells the player
# which habit to break. The summary after a match always shows what the AI learned. `H` toggles it.
LEARN_MODE_DEFAULT = False

# Start of a match: hold a hand still this long (seconds) and the round begins by itself
HOLD_TO_START_SECONDS = 2.0

# Walking away: after this long without a hand or key, ask "Still there?", then return to the start screen
IDLE_SECONDS = 20
IDLE_WARNING_SECONDS = 8

# Settings the operator can change with Ctrl+A. Saved here so they survive a restart.
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
MATCH_ROUND_CHOICES = [10, 15, 20, 0]      # 0 = no limit
IDLE_SECOND_CHOICES = [10, 20, 30]
LEADERBOARD_SIZE = 8
