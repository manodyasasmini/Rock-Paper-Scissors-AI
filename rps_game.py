import cv2
import mediapipe as mp
import numpy as np
import time
import random
import math
import json
import os
import sys
from collections import Counter, defaultdict, deque
from PIL import Image, ImageDraw, ImageFont

# ==========================================================
# 1. INITIALIZATION & SETUP
# ==========================================================
DATA_FILE = "players_data.json"

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.6
)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not cap.isOpened():
    print("ERROR: Could not open the camera. Check that it is connected and not used by another app.")
    sys.exit(1)

WINDOW_NAME = "Rock Paper Scissors AI - Arena"
cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
is_fullscreen = True

# Game constants
CHOICES = ["ROCK", "PAPER", "SCISSORS"]
CHOICE_ICONS = {
    "ROCK": "ROCK [✊]",
    "PAPER": "PAPER [✋]",
    "SCISSORS": "SCISSORS [✌️]"
}
BEATS = {"ROCK": "SCISSORS", "PAPER": "ROCK", "SCISSORS": "PAPER"}

# Game States
STATE_NAME_INPUT = "NAME_INPUT"          # Entering player name
STATE_SESSION_CHOICE = "SESSION_CHOICE"  # Choose Start New vs Resume
STATE_IDLE = "IDLE"                      # Waiting for player to press SPACE
STATE_COUNTDOWN = "COUNTDOWN"            # 3, 2, 1 countdown
STATE_SHOW_RESULT = "RESULT"              # Showing winner of current round

game_state = STATE_NAME_INPUT
countdown_duration = 3.0
state_start_time = 0.0

# Active Player Profile
player_name = "Player 1"
temp_player_name = "Player 1"
input_text = ""
score_player = 0
score_ai = 0
score_ties = 0
streak = 0
best_streak = 0
match_history = deque(maxlen=6)

prev_score_player = 0
prev_score_ai = 0
prev_score_ties = 0
prev_best_streak = 0

player_move = None
ai_move = None
round_result = None

# AI Engine
ai_mode = "Predictive"
transitions = defaultdict(lambda: {"ROCK": 1, "PAPER": 1, "SCISSORS": 1})
last_player_move = None

# Landmark indices
WRIST = 0
FINGER_TIPS = [8, 12, 16, 20]
FINGER_PIPS = [6, 10, 14, 18]

# Gesture smoothing: the move is the most common gesture over the last few frames
GESTURE_WINDOW = 10
GESTURE_MIN_VOTES = 6
gesture_buffer = deque(maxlen=GESTURE_WINDOW)

# Load Crisp TrueType Fonts
def get_font(size, bold=False):
    font_names = [
        "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\trebucbd.ttf" if bold else "C:\\Windows\\Fonts\\trebuc.ttf"
    ]
    for font_path in font_names:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            continue
    return ImageFont.load_default()

FONT_TITLE = get_font(24, bold=True)
FONT_SCORE = get_font(30, bold=True)
FONT_LABEL = get_font(16, bold=False)
FONT_LABEL_BOLD = get_font(18, bold=True)
FONT_BIG_COUNT = get_font(90, bold=True)
FONT_BANNER = get_font(44, bold=True)
FONT_SUB_BANNER = get_font(20, bold=False)
FONT_CARD_TITLE = get_font(20, bold=True)
FONT_CARD_MOVE = get_font(32, bold=True)
FONT_HISTORY = get_font(13, bold=True)
FONT_INPUT = get_font(34, bold=True)
FONT_MODAL_TITLE = get_font(28, bold=True)

# ==========================================================
# 2. PERSISTENT PLAYER DATA & AI MEMORY STORAGE
# ==========================================================
def load_all_players():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Keep the unreadable file so a later save can't silently destroy it
        backup = f"{DATA_FILE}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            os.replace(DATA_FILE, backup)
            print(f"WARNING: {DATA_FILE} was unreadable; moved to {backup}")
        except OSError:
            pass
        return {}

def save_current_player():
    global player_name, transitions, score_player, score_ai, score_ties, best_streak
    if not player_name:
        return
    data = load_all_players()
    
    serialized_transitions = {}
    for k, v in transitions.items():
        serialized_transitions[k] = dict(v)

    data[player_name] = {
        "score_player": score_player,
        "score_ai": score_ai,
        "score_ties": score_ties,
        "best_streak": best_streak,
        "transitions": serialized_transitions,
        "last_played": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    # Write to a temp file then swap it in, so a crash mid-write can't corrupt the data
    tmp_file = DATA_FILE + ".tmp"
    with open(tmp_file, "w") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp_file, DATA_FILE)

def switch_to_player(name, resume_scores=False):
    global player_name, score_player, score_ai, score_ties, streak, best_streak, transitions, match_history, last_player_move
    player_name = name.strip() if name.strip() else "Player 1"
    data = load_all_players()
    
    match_history.clear()
    streak = 0
    last_player_move = None
    transitions = defaultdict(lambda: {"ROCK": 1, "PAPER": 1, "SCISSORS": 1})

    if player_name in data:
        p_data = data[player_name]
        best_streak = p_data.get("best_streak", 0)
        
        if resume_scores:
            score_player = p_data.get("score_player", 0)
            score_ai = p_data.get("score_ai", 0)
            score_ties = p_data.get("score_ties", 0)
        else:
            score_player = 0
            score_ai = 0
            score_ties = 0
        
        saved_trans = p_data.get("transitions", {})
        for move, counts in saved_trans.items():
            transitions[move] = defaultdict(lambda: 1, counts)
    else:
        score_player = 0
        score_ai = 0
        score_ties = 0
        best_streak = 0
        save_current_player()

# ==========================================================
# 3. GAME LOGIC & PREDICTION
# ==========================================================
def detect_gesture(hand_landmarks):
    landmarks = hand_landmarks.landmark
    wrist = landmarks[WRIST]

    def dist_to_wrist(idx):
        return math.hypot(landmarks[idx].x - wrist.x, landmarks[idx].y - wrist.y)

    # A finger is extended when its tip is farther from the wrist than its middle
    # knuckle. Unlike comparing y-coordinates, this works at any hand rotation.
    fingers_extended = []
    for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
        fingers_extended.append(dist_to_wrist(tip) > dist_to_wrist(pip) * 1.05)

    open_count = sum(fingers_extended)

    if open_count == 0:
        return "ROCK"
    elif open_count >= 4:
        return "PAPER"
    elif fingers_extended[0] and fingers_extended[1] and not fingers_extended[2] and not fingers_extended[3]:
        return "SCISSORS"
    else:
        return None

def smooth_gesture(raw_gesture):
    """Record this frame's gesture and return the stable one (or None if unsure)."""
    gesture_buffer.append(raw_gesture)
    votes = Counter(g for g in gesture_buffer if g is not None)
    if not votes:
        return None
    gesture, count = votes.most_common(1)[0]
    return gesture if count >= GESTURE_MIN_VOTES else None

def predict_ai_move():
    global last_player_move, ai_mode
    if ai_mode == "Random" or last_player_move is None:
        return random.choice(CHOICES)

    counts = transitions[last_player_move]
    predicted_player_move = max(counts, key=lambda k: counts[k] + random.uniform(0, 0.1))
    counters = {"ROCK": "PAPER", "PAPER": "SCISSORS", "SCISSORS": "ROCK"}
    return counters[predicted_player_move]

def update_history(current_move):
    global last_player_move
    if last_player_move is not None and current_move in CHOICES:
        transitions[last_player_move][current_move] += 1
    last_player_move = current_move
    save_current_player()

def determine_winner(p_move, a_move):
    if p_move not in CHOICES:
        return "INVALID"
    if p_move == a_move:
        return "TIE"
    elif BEATS[p_move] == a_move:
        return "PLAYER"
    else:
        return "AI"

# ==========================================================
# 4. ADVANCED UI DRAWING ENGINE (PIL + OpenCV)
# ==========================================================
def draw_cyber_hand(frame, hand_landmarks):
    h, w, _ = frame.shape
    points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]

    for conn in mp_hands.HAND_CONNECTIONS:
        pt1 = points[conn[0]]
        pt2 = points[conn[1]]
        cv2.line(frame, pt1, pt2, (255, 200, 0), 3, cv2.LINE_AA)
        cv2.line(frame, pt1, pt2, (255, 255, 255), 1, cv2.LINE_AA)

    for pt in points:
        cv2.circle(frame, pt, 5, (0, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, pt, 2, (255, 255, 255), -1, cv2.LINE_AA)

_background_cache = {}

def get_background(w, h):
    if (w, h) not in _background_cache:
        bg = Image.new("RGBA", (w, h), (12, 16, 26, 255))
        bg_draw = ImageDraw.Draw(bg)
        grid_color = (16, 22, 35, 255)  # grid lines pre-blended onto the background
        for gx in range(0, w, 80):
            bg_draw.line([(gx, 0), (gx, h)], fill=grid_color, width=1)
        for gy in range(0, h, 80):
            bg_draw.line([(0, gy), (w, gy)], fill=grid_color, width=1)
        _background_cache[(w, h)] = bg
    return _background_cache[(w, h)]

def render_ui(frame, current_time, live_gesture):
    h, w, _ = frame.shape

    # Dark arena background with grid, rendered once per resolution and reused
    pil_frame = get_background(w, h).copy()
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # -------------------------------------------------------------
    # STATE 1: NAME INPUT PROFILE SCREEN
    # -------------------------------------------------------------
    if game_state == STATE_NAME_INPUT:
        draw.text((w // 2, 70), "ROCK PAPER SCISSORS AI", font=FONT_BANNER, fill=(35, 55, 90, 180), anchor="mm")

        modal_w, modal_h = 580, 280
        mx1 = (w - modal_w) // 2
        my1 = (h - modal_h) // 2
        mx2 = mx1 + modal_w
        my2 = my1 + modal_h

        draw.rounded_rectangle([mx1 - 4, my1 - 4, mx2 + 4, my2 + 4], radius=24, fill=(0, 240, 255, 60))
        draw.rounded_rectangle([mx1, my1, mx2, my2], radius=20, fill=(15, 18, 28, 250), outline=(0, 240, 255, 255), width=2)

        draw.text((mx1 + modal_w // 2, my1 + 35), "PLAYER PROFILE LOGIN", font=FONT_TITLE, fill=(255, 255, 255, 255), anchor="mm")
        draw.text((mx1 + modal_w // 2, my1 + 72), "AI remembers unique habits & scores for each player", font=FONT_LABEL, fill=(160, 180, 210, 255), anchor="mm")

        ib_x1, ib_y1, ib_x2, ib_y2 = mx1 + 40, my1 + 105, mx2 - 40, my1 + 175
        draw.rounded_rectangle([ib_x1, ib_y1, ib_x2, ib_y2], radius=12, fill=(25, 32, 48, 240), outline=(70, 90, 130, 255), width=2)
        
        cursor = "_" if int(current_time * 2) % 2 == 0 else ""
        display_name = (input_text if input_text else "Enter Name...") + cursor
        text_color = (0, 255, 220, 255) if input_text else (120, 140, 170, 255)
        draw.text((ib_x1 + 20, ib_y1 + 16), display_name, font=FONT_INPUT, fill=text_color)

        draw.text((mx1 + modal_w // 2, my1 + 225), "Press [ENTER] to Confirm   |   [ESC] Use Guest", font=FONT_LABEL_BOLD, fill=(255, 200, 0, 255), anchor="mm")

        final_img = Image.alpha_composite(pil_frame, overlay)
        return cv2.cvtColor(np.array(final_img.convert("RGB")), cv2.COLOR_RGB2BGR)

    # -------------------------------------------------------------
    # STATE 2: RETURNING PLAYER SESSION CHOICE SCREEN
    # -------------------------------------------------------------
    elif game_state == STATE_SESSION_CHOICE:
        draw.text((w // 2, 70), "ROCK PAPER SCISSORS AI", font=FONT_BANNER, fill=(35, 55, 90, 180), anchor="mm")

        modal_w, modal_h = 680, 340
        mx1 = (w - modal_w) // 2
        my1 = (h - modal_h) // 2
        mx2 = mx1 + modal_w
        my2 = my1 + modal_h

        draw.rounded_rectangle([mx1 - 4, my1 - 4, mx2 + 4, my2 + 4], radius=24, fill=(0, 240, 255, 70))
        draw.rounded_rectangle([mx1, my1, mx2, my2], radius=20, fill=(15, 18, 28, 250), outline=(0, 240, 255, 255), width=2)

        draw.text((mx1 + modal_w // 2, my1 + 35), f"WELCOME BACK, {temp_player_name.upper()}!", font=FONT_MODAL_TITLE, fill=(0, 240, 255, 255), anchor="mm")
        
        stats_text = f"Previous Session: YOU {prev_score_player}  |  AI {prev_score_ai}  |  TIES {prev_score_ties}   (Best Streak: {prev_best_streak})"
        draw.text((mx1 + modal_w // 2, my1 + 75), stats_text, font=FONT_LABEL, fill=(200, 215, 240, 255), anchor="mm")

        b1_x1, b1_y1, b1_x2, b1_y2 = mx1 + 40, my1 + 115, mx2 - 40, my1 + 185
        draw.rounded_rectangle([b1_x1, b1_y1, b1_x2, b1_y2], radius=14, fill=(15, 45, 60, 240), outline=(0, 230, 255, 255), width=2)
        draw.text((b1_x1 + 25, b1_y1 + 14), "[ENTER] or [N]  START NEW GAME", font=FONT_LABEL_BOLD, fill=(0, 255, 220, 255))
        draw.text((b1_x1 + 25, b1_y1 + 42), "Reset scores to 0-0  (Keeps AI learned habits & best streak record)", font=FONT_LABEL, fill=(180, 210, 230, 255))

        b2_x1, b2_y1, b2_x2, b2_y2 = mx1 + 40, my1 + 205, mx2 - 40, my1 + 275
        draw.rounded_rectangle([b2_x1, b2_y1, b2_x2, b2_y2], radius=14, fill=(45, 20, 45, 240), outline=(240, 80, 220, 255), width=2)
        draw.text((b2_x1 + 25, b2_y1 + 14), "[C]  CONTINUE / RESUME SCORES", font=FONT_LABEL_BOLD, fill=(255, 120, 240, 255))
        draw.text((b2_x1 + 25, b2_y1 + 42), f"Resume previous scores (YOU: {prev_score_player} | AI: {prev_score_ai} | TIES: {prev_score_ties})", font=FONT_LABEL, fill=(220, 190, 220, 255))

        draw.text((mx1 + modal_w // 2, my1 + 305), "Press [ESC] to change name", font=FONT_LABEL, fill=(140, 150, 175, 255), anchor="mm")

        final_img = Image.alpha_composite(pil_frame, overlay)
        return cv2.cvtColor(np.array(final_img.convert("RGB")), cv2.COLOR_RGB2BGR)

    # -------------------------------------------------------------
    # A. TOP SCOREBOARD DOCK (Glassmorphic Dark Panel with Neon Border)
    # -------------------------------------------------------------
    bar_x1, bar_y1, bar_x2, bar_y2 = 30, 18, w - 30, 120
    draw.rounded_rectangle([bar_x1, bar_y1, bar_x2, bar_y2], radius=20, fill=(15, 17, 24, 235), outline=(60, 70, 95, 255), width=2)
    draw.line([(bar_x1 + 30, bar_y1 + 2), (w // 2, bar_y1 + 2)], fill=(0, 240, 255, 255), width=3)
    draw.line([(w // 2, bar_y1 + 2), (bar_x2 - 30, bar_y1 + 2)], fill=(240, 60, 255, 255), width=3)

    # Left: Player Name & AI Mode Tag
    draw.text((bar_x1 + 25, bar_y1 + 16), f"PLAYER: {player_name.upper()}", font=FONT_TITLE, fill=(255, 255, 255, 255))
    
    mode_color = (0, 230, 180, 255) if ai_mode == "Predictive" else (220, 220, 220, 255)
    ai_tag = f"AI: {ai_mode.upper()} [D to toggle]"
    t_left, t_top, t_right, t_bottom = draw.textbbox((0, 0), ai_tag, font=FONT_LABEL)
    tag_w = (t_right - t_left) + 40
    pill_x1 = bar_x1 + 25
    pill_y1 = bar_y1 + 54
    pill_x2 = pill_x1 + tag_w
    pill_y2 = pill_y1 + 32
    
    draw.rounded_rectangle([pill_x1, pill_y1, pill_x2, pill_y2], radius=10, fill=(30, 36, 50, 240), outline=(60, 75, 105, 255), width=1)
    draw.ellipse([pill_x1 + 12, pill_y1 + 11, pill_x1 + 22, pill_y1 + 21], fill=mode_color)
    draw.text((pill_x1 + 28, pill_y1 + 5), ai_tag, font=FONT_LABEL, fill=mode_color)

    # Center: Battle Score Badges (Player vs AI)
    center_x = w // 2
    draw.rounded_rectangle([center_x - 170, bar_y1 + 20, center_x - 45, bar_y1 + 86], radius=12, fill=(10, 45, 65, 230), outline=(0, 220, 255, 255), width=2)
    draw.text((center_x - 158, bar_y1 + 24), "YOU", font=FONT_LABEL_BOLD, fill=(0, 220, 255, 255))
    draw.text((center_x - 85, bar_y1 + 28), str(score_player), font=FONT_SCORE, fill=(255, 255, 255, 255))

    draw.text((center_x - 20, bar_y1 + 38), "VS", font=FONT_LABEL_BOLD, fill=(140, 150, 180, 255))

    draw.rounded_rectangle([center_x + 45, bar_y1 + 20, center_x + 170, bar_y1 + 86], radius=12, fill=(65, 15, 35, 230), outline=(255, 60, 110, 255), width=2)
    draw.text((center_x + 58, bar_y1 + 24), "AI", font=FONT_LABEL_BOLD, fill=(255, 80, 130, 255))
    draw.text((center_x + 130, bar_y1 + 28), str(score_ai), font=FONT_SCORE, fill=(255, 255, 255, 255))

    # Right: Streak & Match History Pills
    streak_str = f"STREAK: {streak}  (Best: {best_streak})"
    s_left, s_top, s_right, s_bottom = draw.textbbox((0, 0), streak_str, font=FONT_LABEL_BOLD)
    s_w = (s_right - s_left) + 45
    s_x2 = bar_x2 - 25
    s_x1 = s_x2 - s_w
    s_y1 = bar_y1 + 16
    s_y2 = s_y1 + 32

    streak_bg = (60, 42, 10, 240) if streak > 0 else (25, 28, 38, 220)
    streak_border = (255, 190, 0, 255) if streak > 0 else (55, 65, 85, 255)
    draw.rounded_rectangle([s_x1, s_y1, s_x2, s_y2], radius=10, fill=streak_bg, outline=streak_border, width=1)
    
    star_col = (255, 210, 50, 255) if streak > 0 else (120, 130, 150, 255)
    draw.ellipse([s_x1 + 12, s_y1 + 11, s_x1 + 22, s_y1 + 21], fill=star_col)
    draw.text((s_x1 + 28, s_y1 + 4), streak_str, font=FONT_LABEL_BOLD, fill=star_col)

    # History Pills
    draw.text((s_x2 - 210, bar_y1 + 68), "RECENT:", font=FONT_LABEL, fill=(140, 150, 175, 255), anchor="lm")
    hx = s_x2 - 130
    badge_size = 22
    by = bar_y1 + 57
    for res in match_history:
        if res == 'W':
            col = (0, 240, 140, 255)
            sym = "W"
        elif res == 'L':
            col = (255, 65, 95, 255)
            sym = "L"
        else:
            col = (255, 200, 0, 255)
            sym = "D"
        draw.rounded_rectangle([hx, by, hx + badge_size, by + badge_size], radius=6, fill=col)
        draw.text((hx + badge_size // 2, by + badge_size // 2), sym, font=FONT_HISTORY, fill=(10, 15, 20, 255), anchor="mm")
        hx += 26

    # -------------------------------------------------------------
    # B. ARENA 3-COLUMN LAYOUT: (YOUR CARD | CAMERA VIEWPORT | AI CARD)
    # -------------------------------------------------------------
    arena_y = 140
    arena_h = h - arena_y - 85

    # 1. Center Camera Viewport with EXACT 100% Natural Aspect Ratio (No distortion)
    frame_h, frame_w, _ = frame.shape
    cam_aspect = frame_w / frame_h if frame_h > 0 else (16 / 9)

    cam_h = min(arena_h - 20, 520)
    cam_w = int(cam_h * cam_aspect)

    # If camera box is too wide, fit by width
    max_cam_w = int(w * 0.52)
    if cam_w > max_cam_w:
        cam_w = max_cam_w
        cam_h = int(cam_w / cam_aspect)

    cam_x = (w - cam_w) // 2
    cam_y = arena_y + (arena_h - cam_h) // 2

    # Resize the camera frame maintaining exact natural proportions
    resized_cam = cv2.resize(frame, (cam_w, cam_h))
    cam_pil = Image.fromarray(cv2.cvtColor(resized_cam, cv2.COLOR_BGR2RGB)).convert("RGBA")
    
    # Paste camera feed into studio canvas
    pil_frame.paste(cam_pil, (cam_x, cam_y))

    # Camera Frame Glowing Border
    draw.rounded_rectangle([cam_x - 3, cam_y - 3, cam_x + cam_w + 3, cam_y + cam_h + 3], radius=16, outline=(0, 220, 255, 200), width=2)
    draw.text((cam_x + 15, cam_y + 14), "LIVE HAND VIEW", font=FONT_LABEL_BOLD, fill=(0, 220, 255, 255))

    # Floating Live Gesture Badge inside Camera Box
    badge_str = f"STATUS: {live_gesture}" if live_gesture else "STATUS: SEARCHING..."
    b_col = (0, 255, 150, 255) if live_gesture else (255, 180, 50, 255)
    draw.rounded_rectangle([cam_x + 15, cam_y + cam_h - 40, cam_x + 230, cam_y + cam_h - 12], radius=8, fill=(15, 18, 28, 220), outline=b_col, width=1)
    draw.ellipse([cam_x + 25, cam_y + cam_h - 30, cam_x + 35, cam_y + cam_h - 20], fill=b_col)
    draw.text((cam_x + 42, cam_y + cam_h - 35), badge_str, font=FONT_LABEL, fill=b_col)

    # 2. Left Column: YOUR ACTION CARD (Beside camera, never overlapping)
    card_w = cam_x - 50
    card_x1 = 30
    card_y1 = cam_y
    card_y2 = cam_y + cam_h

    # Card Background Frame (Cyan Theme)
    draw.rounded_rectangle([card_x1 - 2, card_y1 - 2, card_x1 + card_w + 2, card_y2 + 2], radius=18, fill=(0, 240, 255, 30))
    draw.rounded_rectangle([card_x1, card_y1, card_x1 + card_w, card_y2], radius=16, fill=(15, 22, 34, 245), outline=(0, 220, 255, 255), width=2)

    draw.text((card_x1 + card_w // 2, card_y1 + 35), "YOUR ACTION", font=FONT_CARD_TITLE, fill=(0, 220, 255, 255), anchor="mm")
    draw.text((card_x1 + card_w // 2, card_y1 + 65), f"PLAYER: {player_name.upper()}", font=FONT_LABEL, fill=(160, 180, 210, 255), anchor="mm")

    # Center Gesture Display Box
    p_box_y1 = card_y1 + 100
    p_box_y2 = card_y2 - 60
    draw.rounded_rectangle([card_x1 + 20, p_box_y1, card_x1 + card_w - 20, p_box_y2], radius=14, fill=(22, 32, 50, 240), outline=(50, 75, 110, 255), width=1)

    if game_state == STATE_SHOW_RESULT:
        p_display = player_move if player_move else "NO MOVE"
        p_display_col = (0, 255, 180, 255) if player_move else (255, 70, 70, 255)
        p_status_msg = "FINAL MOVE"
    else:
        p_display = live_gesture if live_gesture else "WAITING"
        p_display_col = (0, 220, 255, 255) if live_gesture else (120, 140, 170, 255)
        p_status_msg = "TRACKING GESTURE"

    draw.text((card_x1 + card_w // 2, (p_box_y1 + p_box_y2) // 2), p_display, font=FONT_CARD_MOVE, fill=p_display_col, anchor="mm")
    draw.text((card_x1 + card_w // 2, card_y2 - 30), p_status_msg, font=FONT_LABEL_BOLD, fill=(180, 200, 230, 255), anchor="mm")

    # 3. Right Column: AI OPPONENT CARD (Beside camera, never overlapping)
    ai_card_x1 = cam_x + cam_w + 20
    ai_card_w = w - ai_card_x1 - 30
    ai_card_y1 = cam_y
    ai_card_y2 = cam_y + cam_h

    # Card Background Frame (Magenta Theme)
    draw.rounded_rectangle([ai_card_x1 - 2, ai_card_y1 - 2, ai_card_x1 + ai_card_w + 2, ai_card_y2 + 2], radius=18, fill=(255, 60, 130, 30))
    draw.rounded_rectangle([ai_card_x1, ai_card_y1, ai_card_x1 + ai_card_w, ai_card_y2], radius=16, fill=(32, 14, 26, 245), outline=(255, 60, 130, 255), width=2)

    draw.text((ai_card_x1 + ai_card_w // 2, ai_card_y1 + 35), "AI OPPONENT", font=FONT_CARD_TITLE, fill=(255, 80, 140, 255), anchor="mm")
    draw.text((ai_card_x1 + ai_card_w // 2, ai_card_y1 + 65), f"NEURAL BOT ({ai_mode.upper()})", font=FONT_LABEL, fill=(220, 160, 190, 255), anchor="mm")

    ai_box_y1 = ai_card_y1 + 100
    ai_box_y2 = ai_card_y2 - 60
    draw.rounded_rectangle([ai_card_x1 + 20, ai_box_y1, ai_card_x1 + ai_card_w - 20, ai_box_y2], radius=14, fill=(48, 20, 38, 240), outline=(110, 50, 85, 255), width=1)

    if game_state == STATE_SHOW_RESULT:
        ai_display = ai_move if ai_move else "NONE"
        ai_display_col = (255, 100, 160, 255)
        ai_status_msg = "COUNTER REVEALED"
    elif game_state == STATE_COUNTDOWN:
        ai_display = "DECIDING..."
        ai_display_col = (255, 180, 80, 255)
        ai_status_msg = "CALCULATING ODDS"
    else:
        ai_display = "READY"
        ai_display_col = (180, 140, 170, 255)
        ai_status_msg = "AWAITING ROUND"

    draw.text((ai_card_x1 + ai_card_w // 2, (ai_box_y1 + ai_box_y2) // 2), ai_display, font=FONT_CARD_MOVE, fill=ai_display_col, anchor="mm")
    draw.text((ai_card_x1 + ai_card_w // 2, ai_card_y2 - 30), ai_status_msg, font=FONT_LABEL_BOLD, fill=(230, 180, 210, 255), anchor="mm")

    # -------------------------------------------------------------
    # C. CENTER COUNTDOWN / RESULT OVERLAYS
    # -------------------------------------------------------------
    if game_state == STATE_IDLE:
        prompt_w, prompt_h = 380, 80
        px1 = cam_x + (cam_w - prompt_w) // 2
        py1 = cam_y + (cam_h - prompt_h) // 2

        draw.rounded_rectangle([px1 - 3, py1 - 3, px1 + prompt_w + 3, py1 + prompt_h + 3], radius=18, fill=(0, 220, 255, 40))
        draw.rounded_rectangle([px1, py1, px1 + prompt_w, py1 + prompt_h], radius=16, fill=(15, 18, 28, 235), outline=(0, 220, 255, 255), width=2)
        
        draw.text((px1 + prompt_w // 2, py1 + 24), "ARE YOU READY?", font=FONT_LABEL_BOLD, fill=(0, 220, 255, 255), anchor="mm")
        draw.text((px1 + prompt_w // 2, py1 + 54), "Press [SPACE] to Start", font=FONT_TITLE, fill=(255, 255, 255, 255), anchor="mm")

    elif game_state == STATE_COUNTDOWN:
        elapsed = current_time - state_start_time
        remaining = countdown_duration - elapsed
        progress = max(0.0, min(1.0, elapsed / countdown_duration))

        c_cx = cam_x + cam_w // 2
        c_cy = cam_y + cam_h // 2

        gauge_r = min(cam_h // 3, 90)
        bbox = [c_cx - gauge_r, c_cy - gauge_r, c_cx + gauge_r, c_cy + gauge_r]
        
        draw.ellipse(bbox, outline=(40, 50, 70, 200), width=8)
        start_angle = -90
        end_angle = start_angle + (360 * (1.0 - progress))
        if end_angle > start_angle:
            draw.arc(bbox, start=start_angle, end=end_angle, fill=(0, 255, 230, 255), width=8)

        if remaining > 2.0:
            count_str = "3"
            color = (0, 255, 255, 255)
        elif remaining > 1.0:
            count_str = "2"
            color = (0, 220, 255, 255)
        elif remaining > 0.0:
            count_str = "1"
            color = (255, 180, 0, 255)
        else:
            count_str = "GO!"
            color = (0, 255, 140, 255)

        draw.text((c_cx, c_cy), count_str, font=FONT_BIG_COUNT, fill=color, anchor="mm")
        draw.text((c_cx, c_cy + gauge_r + 25), "SHOW GESTURE NOW!", font=FONT_LABEL_BOLD, fill=(255, 255, 255, 255), anchor="mm")

    elif game_state == STATE_SHOW_RESULT:
        banner_w, banner_h = min(cam_w - 40, 480), 120
        bx = cam_x + (cam_w - banner_w) // 2
        by = cam_y + (cam_h - banner_h) // 2 - 10

        if round_result == "PLAYER":
            res_title = "VICTORY!"
            res_sub = f"+1 Point to {player_name.upper()}"
            banner_bg = (10, 45, 30, 245)
            banner_border = (0, 255, 140, 255)
            text_color = (0, 255, 160, 255)
        elif round_result == "AI":
            res_title = "AI WINS!"
            res_sub = "+1 Point to AI Bot"
            banner_bg = (45, 10, 20, 245)
            banner_border = (255, 60, 80, 255)
            text_color = (255, 75, 95, 255)
        elif round_result == "TIE":
            res_title = "DRAW MATCH!"
            res_sub = "Both chose the same move"
            banner_bg = (45, 35, 10, 245)
            banner_border = (255, 200, 0, 255)
            text_color = (255, 215, 0, 255)
        else:
            res_title = "NO DETECTION"
            res_sub = "Keep hand visible in camera box"
            banner_bg = (35, 20, 10, 245)
            banner_border = (255, 120, 0, 255)
            text_color = (255, 140, 30, 255)

        draw.rounded_rectangle([bx - 3, by - 3, bx + banner_w + 3, by + banner_h + 3], radius=20, fill=banner_border)
        draw.rounded_rectangle([bx, by, bx + banner_w, by + banner_h], radius=18, fill=banner_bg)

        draw.text((bx + banner_w // 2, by + 40), res_title, font=FONT_BANNER, fill=text_color, anchor="mm")
        draw.text((bx + banner_w // 2, by + 85), res_sub, font=FONT_SUB_BANNER, fill=(220, 230, 240, 255), anchor="mm")

        prompt_next = "Press [SPACE] for Next Round"
        draw.text((bx + banner_w // 2, by + banner_h + 30), prompt_next, font=FONT_LABEL_BOLD, fill=(0, 255, 220, 255), anchor="mm")

    # -------------------------------------------------------------
    # D. BOTTOM CONTROLS DOCK (Sleek Glass Dock)
    # -------------------------------------------------------------
    dock_h = 46
    dock_w = min(w - 60, 1080)
    dx1 = (w - dock_w) // 2
    dy1 = h - dock_h - 16
    dx2 = dx1 + dock_w
    dy2 = dy1 + dock_h

    draw.rounded_rectangle([dx1, dy1, dx2, dy2], radius=14, fill=(15, 17, 24, 225), outline=(50, 60, 80, 255), width=1)
    
    controls = [
        ("[SPACE]", "Play Round"),
        ("[P]", "Switch Player"),
        ("[F]", "Fullscreen"),
        ("[D]", "Toggle AI"),
        ("[R]", "Reset"),
        ("[Q]", "Quit")
    ]
    step = dock_w // len(controls)
    for i, (key_label, desc) in enumerate(controls):
        cx = dx1 + i * step + step // 2
        text = f"{key_label} {desc}"
        left, top, right, bottom = draw.textbbox((0, 0), text, font=FONT_LABEL)
        tw = right - left
        draw.text((cx - tw // 2, dy1 + 13), text, font=FONT_LABEL, fill=(210, 220, 240, 255))

    final_img = Image.alpha_composite(pil_frame, overlay)
    return cv2.cvtColor(np.array(final_img.convert("RGB")), cv2.COLOR_RGB2BGR)

# ==========================================================
# 5. MAIN GAME LOOP
# ==========================================================
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

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    current_time = time.time()

    # Process hand landmarks only during active gameplay
    live_gesture = None
    if game_state not in [STATE_NAME_INPUT, STATE_SESSION_CHOICE]:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        raw_gesture = None
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                draw_cyber_hand(frame, hand_landmarks)
                raw_gesture = detect_gesture(hand_landmarks)
        live_gesture = smooth_gesture(raw_gesture)
    else:
        gesture_buffer.clear()

    # --- STATE TRANSITIONS ---
    if game_state == STATE_COUNTDOWN:
        elapsed = current_time - state_start_time
        remaining = countdown_duration - elapsed

        if remaining <= 0:
            player_move = live_gesture
            ai_move = predict_ai_move()
            round_result = determine_winner(player_move, ai_move)

            if round_result == "PLAYER":
                score_player += 1
                streak += 1
                best_streak = max(best_streak, streak)
                match_history.append('W')
            elif round_result == "AI":
                score_ai += 1
                streak = 0
                match_history.append('L')
            elif round_result == "TIE":
                score_ties += 1
                match_history.append('D')

            if player_move in CHOICES:
                update_history(player_move)
            else:
                save_current_player()

            game_state = STATE_SHOW_RESULT
            state_start_time = current_time

    # Render Cyber UI
    display_frame = render_ui(frame, current_time, live_gesture)

    cv2.imshow(WINDOW_NAME, display_frame)

    # Key controls
    key = cv2.waitKey(1) & 0xFF

    # 1. Text input handling during Player Profile Screen
    if game_state == STATE_NAME_INPUT:
        if key == 13:  # ENTER
            chosen_name = input_text.strip() if input_text.strip() else "Player 1"
            all_players = load_all_players()
            if chosen_name in all_players:
                temp_player_name = chosen_name
                p_data = all_players[chosen_name]
                prev_score_player = p_data.get("score_player", 0)
                prev_score_ai = p_data.get("score_ai", 0)
                prev_score_ties = p_data.get("score_ties", 0)
                prev_best_streak = p_data.get("best_streak", 0)
                game_state = STATE_SESSION_CHOICE
            else:
                switch_to_player(chosen_name, resume_scores=False)
                game_state = STATE_IDLE
        elif key == 27:  # ESC (Use Guest)
            switch_to_player("Guest", resume_scores=False)
            game_state = STATE_IDLE
        elif key == 8:  # BACKSPACE
            input_text = input_text[:-1]
        elif 32 <= key <= 126 and len(input_text) < 14:  # Printable character
            input_text += chr(key)
        continue

    # 2. Returning Player Choice: Start New vs Resume
    elif game_state == STATE_SESSION_CHOICE:
        if key == 13 or key == ord('n') or key == ord('N'):  # ENTER or N: Start Fresh
            switch_to_player(temp_player_name, resume_scores=False)
            game_state = STATE_IDLE
        elif key == ord('c') or key == ord('C'):  # C: Continue / Resume
            switch_to_player(temp_player_name, resume_scores=True)
            game_state = STATE_IDLE
        elif key == 27 or key == ord('b') or key == ord('B'):  # ESC: Back
            game_state = STATE_NAME_INPUT
        continue

    # 3. In-Game Controls
    if key == ord('q') or key == ord('Q'):
        save_current_player()
        break
    elif key == ord('p') or key == ord('P'):
        save_current_player()
        input_text = player_name
        game_state = STATE_NAME_INPUT
    elif key == ord('f') or key == ord('F'):
        is_fullscreen = not is_fullscreen
        prop = cv2.WINDOW_FULLSCREEN if is_fullscreen else cv2.WINDOW_NORMAL
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, prop)
    elif key == 32:  # SPACE - Start Round from IDLE or RESULT
        if game_state in [STATE_IDLE, STATE_SHOW_RESULT]:
            game_state = STATE_COUNTDOWN
            state_start_time = time.time()
    elif key == ord('d') or key == ord('D'):
        ai_mode = "Random" if ai_mode == "Predictive" else "Predictive"
    elif key == ord('r') or key == ord('R'):
        score_player = 0
        score_ai = 0
        score_ties = 0
        streak = 0
        match_history.clear()
        save_current_player()
        game_state = STATE_IDLE

save_current_player()
cap.release()
cv2.destroyAllWindows()
