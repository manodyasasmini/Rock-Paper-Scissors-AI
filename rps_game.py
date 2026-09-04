import cv2
import mediapipe as mp
import numpy as np
import time
import random
import math
import json
import os
from collections import defaultdict, deque
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

WINDOW_NAME = "Rock Paper Scissors AI - Arena"
cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
is_fullscreen = True

# Game constants
CHOICES = ["ROCK", "PAPER", "SCISSORS"]
BEATS = {"ROCK": "SCISSORS", "PAPER": "ROCK", "SCISSORS": "PAPER"}

# Game States
STATE_NAME_INPUT = "NAME_INPUT"  # Entering player name at start / switch
STATE_IDLE = "IDLE"              # Waiting for player to press SPACE
STATE_COUNTDOWN = "COUNTDOWN"    # 3, 2, 1 countdown
STATE_SHOW_RESULT = "RESULT"      # Showing winner of current round

game_state = STATE_NAME_INPUT
countdown_duration = 3.0
state_start_time = 0.0
result_display_duration = 3.5

# Active Player Profile
player_name = "Player 1"
input_text = ""
score_player = 0
score_ai = 0
score_ties = 0
streak = 0
best_streak = 0
match_history = deque(maxlen=6)  # Stores ('W', 'L', 'D')

player_move = None
ai_move = None
round_result = None

# AI Engine
ai_mode = "Predictive"  # "Predictive" or "Random"
transitions = defaultdict(lambda: {"ROCK": 1, "PAPER": 1, "SCISSORS": 1})
last_player_move = None

# Landmark indices
FINGER_TIPS = [8, 12, 16, 20]
FINGER_PIPS = [6, 10, 14, 18]

# Load Crisp Fonts using PIL
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

FONT_TITLE = get_font(26, bold=True)
FONT_SCORE = get_font(32, bold=True)
FONT_LABEL = get_font(18, bold=False)
FONT_LABEL_BOLD = get_font(20, bold=True)
FONT_BIG_COUNT = get_font(110, bold=True)
FONT_BANNER = get_font(52, bold=True)
FONT_SUB_BANNER = get_font(24, bold=False)
FONT_CARD_TITLE = get_font(22, bold=True)
FONT_CARD_MOVE = get_font(36, bold=True)
FONT_HISTORY = get_font(13, bold=True)
FONT_INPUT = get_font(38, bold=True)

# ==========================================================
# 2. PERSISTENT PLAYER DATA & AI MEMORY STORAGE
# ==========================================================
def load_all_players():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_current_player():
    global player_name, transitions, score_player, score_ai, score_ties, best_streak
    if not player_name:
        return
    data = load_all_players()
    
    # Format transitions into plain dict for JSON serialization
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
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def switch_to_player(name):
    global player_name, score_player, score_ai, score_ties, streak, best_streak, transitions, match_history, last_player_move
    player_name = name.strip() if name.strip() else "Player 1"
    data = load_all_players()
    
    match_history.clear()
    streak = 0
    last_player_move = None
    transitions = defaultdict(lambda: {"ROCK": 1, "PAPER": 1, "SCISSORS": 1})

    if player_name in data:
        p_data = data[player_name]
        score_player = p_data.get("score_player", 0)
        score_ai = p_data.get("score_ai", 0)
        score_ties = p_data.get("score_ties", 0)
        best_streak = p_data.get("best_streak", 0)
        
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
    fingers_extended = []
    for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
        is_extended = landmarks[tip].y < landmarks[pip].y
        fingers_extended.append(is_extended)

    open_count = sum(fingers_extended)

    if open_count == 0:
        return "ROCK"
    elif open_count >= 4:
        return "PAPER"
    elif fingers_extended[0] and fingers_extended[1] and not fingers_extended[2] and not fingers_extended[3]:
        return "SCISSORS"
    else:
        return None

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

def render_ui(frame, current_time, live_gesture):
    h, w, _ = frame.shape

    pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # -------------------------------------------------------------
    # STATE: NAME INPUT PROFILE SCREEN
    # -------------------------------------------------------------
    if game_state == STATE_NAME_INPUT:
        # Full dark glass modal in center
        modal_w, modal_h = 580, 280
        mx1 = (w - modal_w) // 2
        my1 = (h - modal_h) // 2
        mx2 = mx1 + modal_w
        my2 = my1 + modal_h

        # Dim background
        draw.rectangle([0, 0, w, h], fill=(5, 8, 15, 200))

        # Modal Box
        draw.rounded_rectangle([mx1 - 4, my1 - 4, mx2 + 4, my2 + 4], radius=24, fill=(0, 240, 255, 50))
        draw.rounded_rectangle([mx1, my1, mx2, my2], radius=20, fill=(15, 18, 28, 245), outline=(0, 240, 255, 255), width=2)

        # Modal Content
        draw.text((mx1 + modal_w // 2, my1 + 35), "PLAYER PROFILE LOGIN", font=FONT_TITLE, fill=(255, 255, 255, 255), anchor="mm")
        draw.text((mx1 + modal_w // 2, my1 + 72), "AI remembers unique patterns & scores for each player", font=FONT_LABEL, fill=(160, 180, 210, 255), anchor="mm")

        # Input Box
        ib_x1, ib_y1, ib_x2, ib_y2 = mx1 + 40, my1 + 105, mx2 - 40, my1 + 175
        draw.rounded_rectangle([ib_x1, ib_y1, ib_x2, ib_y2], radius=12, fill=(25, 32, 48, 240), outline=(70, 90, 130, 255), width=2)
        
        # Display typed name + blinking cursor
        cursor = "_" if int(current_time * 2) % 2 == 0 else ""
        display_name = (input_text if input_text else "Enter Name...") + cursor
        text_color = (0, 255, 220, 255) if input_text else (120, 140, 170, 255)
        draw.text((ib_x1 + 20, ib_y1 + 14), display_name, font=FONT_INPUT, fill=text_color)

        # Helper
        draw.text((mx1 + modal_w // 2, my1 + 225), "Press [ENTER] to Confirm   |   [ESC] Use Guest", font=FONT_LABEL_BOLD, fill=(255, 200, 0, 255), anchor="mm")

        final_img = Image.alpha_composite(pil_frame, overlay)
        return cv2.cvtColor(np.array(final_img.convert("RGB")), cv2.COLOR_RGB2BGR)

    # -------------------------------------------------------------
    # A. TOP SCOREBOARD DOCK (Glassmorphic Dark Panel with Neon Border)
    # -------------------------------------------------------------
    bar_x1, bar_y1, bar_x2, bar_y2 = 30, 18, w - 30, 126
    draw.rounded_rectangle([bar_x1, bar_y1, bar_x2, bar_y2], radius=20, fill=(15, 17, 24, 225), outline=(60, 70, 95, 255), width=2)
    draw.line([(bar_x1 + 30, bar_y1 + 2), (w // 2, bar_y1 + 2)], fill=(0, 240, 255, 255), width=3)
    draw.line([(w // 2, bar_y1 + 2), (bar_x2 - 30, bar_y1 + 2)], fill=(240, 60, 255, 255), width=3)

    # Left: Player Name & AI Mode Tag
    draw.text((bar_x1 + 25, bar_y1 + 16), f"PLAYER: {player_name.upper()}", font=FONT_TITLE, fill=(255, 255, 255, 255))
    
    # Dynamic AI Mode Pill
    mode_color = (0, 230, 180, 255) if ai_mode == "Predictive" else (220, 220, 220, 255)
    ai_tag = f"AI: {ai_mode.upper()} [D to toggle]"
    t_left, t_top, t_right, t_bottom = draw.textbbox((0, 0), ai_tag, font=FONT_LABEL)
    tag_w = (t_right - t_left) + 40
    pill_x1 = bar_x1 + 25
    pill_y1 = bar_y1 + 58
    pill_x2 = pill_x1 + tag_w
    pill_y2 = pill_y1 + 32
    
    draw.rounded_rectangle([pill_x1, pill_y1, pill_x2, pill_y2], radius=10, fill=(30, 36, 50, 240), outline=(60, 75, 105, 255), width=1)
    draw.ellipse([pill_x1 + 12, pill_y1 + 11, pill_x1 + 22, pill_y1 + 21], fill=mode_color)
    draw.text((pill_x1 + 28, pill_y1 + 5), ai_tag, font=FONT_LABEL, fill=mode_color)

    # Center: Battle Score Badges (Player vs AI)
    center_x = w // 2
    draw.rounded_rectangle([center_x - 170, bar_y1 + 22, center_x - 45, bar_y1 + 90], radius=12, fill=(10, 45, 65, 230), outline=(0, 220, 255, 255), width=2)
    draw.text((center_x - 158, bar_y1 + 26), "YOU", font=FONT_LABEL_BOLD, fill=(0, 220, 255, 255))
    draw.text((center_x - 85, bar_y1 + 32), str(score_player), font=FONT_SCORE, fill=(255, 255, 255, 255))

    draw.text((center_x - 20, bar_y1 + 40), "VS", font=FONT_LABEL_BOLD, fill=(140, 150, 180, 255))

    draw.rounded_rectangle([center_x + 45, bar_y1 + 22, center_x + 170, bar_y1 + 90], radius=12, fill=(65, 15, 35, 230), outline=(255, 60, 110, 255), width=2)
    draw.text((center_x + 58, bar_y1 + 26), "AI", font=FONT_LABEL_BOLD, fill=(255, 80, 130, 255))
    draw.text((center_x + 130, bar_y1 + 32), str(score_ai), font=FONT_SCORE, fill=(255, 255, 255, 255))

    # Right: Streak & Match History Pills
    streak_str = f"STREAK: {streak}  (Best: {best_streak})"
    s_left, s_top, s_right, s_bottom = draw.textbbox((0, 0), streak_str, font=FONT_LABEL_BOLD)
    s_w = (s_right - s_left) + 45
    s_x2 = bar_x2 - 25
    s_x1 = s_x2 - s_w
    s_y1 = bar_y1 + 18
    s_y2 = s_y1 + 34

    streak_bg = (60, 42, 10, 240) if streak > 0 else (25, 28, 38, 220)
    streak_border = (255, 190, 0, 255) if streak > 0 else (55, 65, 85, 255)
    draw.rounded_rectangle([s_x1, s_y1, s_x2, s_y2], radius=10, fill=streak_bg, outline=streak_border, width=1)
    
    star_col = (255, 210, 50, 255) if streak > 0 else (120, 130, 150, 255)
    draw.ellipse([s_x1 + 12, s_y1 + 12, s_x1 + 22, s_y1 + 22], fill=star_col)
    draw.text((s_x1 + 28, s_y1 + 5), streak_str, font=FONT_LABEL_BOLD, fill=star_col)

    # History Pills
    draw.text((s_x2 - 210, bar_y1 + 72), "RECENT:", font=FONT_LABEL, fill=(140, 150, 175, 255), anchor="lm")
    hx = s_x2 - 130
    badge_size = 22
    by = bar_y1 + 61
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
    # B. LIVE HAND STATUS FLOATING WIDGET (Bottom-Left)
    # -------------------------------------------------------------
    hw_x1, hw_y1, hw_x2, hw_y2 = 30, h - 145, 300, h - 85
    draw.rounded_rectangle([hw_x1, hw_y1, hw_x2, hw_y2], radius=15, fill=(15, 17, 24, 210), outline=(50, 60, 80, 255), width=2)
    
    if live_gesture:
        draw.ellipse([hw_x1 + 18, hw_y1 + 22, hw_x1 + 30, hw_y1 + 34], fill=(0, 255, 150, 255))
        draw.text((hw_x1 + 38, hw_y1 + 14), "HAND DETECTED", font=FONT_LABEL, fill=(0, 255, 150, 255))
        draw.text((hw_x1 + 38, hw_y1 + 32), live_gesture, font=FONT_LABEL_BOLD, fill=(255, 255, 255, 255))
    else:
        pulse_alpha = int(150 + 105 * math.sin(current_time * 5))
        draw.ellipse([hw_x1 + 18, hw_y1 + 22, hw_x1 + 30, hw_y1 + 34], fill=(255, 160, 0, pulse_alpha))
        draw.text((hw_x1 + 38, hw_y1 + 14), "SEARCHING HAND...", font=FONT_LABEL, fill=(255, 180, 50, 255))
        draw.text((hw_x1 + 38, hw_y1 + 32), "Show hand in camera", font=FONT_LABEL, fill=(160, 170, 190, 255))

    # -------------------------------------------------------------
    # C. CENTER ARENA STATE DISPLAYS
    # -------------------------------------------------------------
    if game_state == STATE_IDLE:
        prompt_w, prompt_h = 480, 110
        px1 = (w - prompt_w) // 2
        py1 = (h - prompt_h) // 2 + 10
        
        draw.rounded_rectangle([px1 - 4, py1 - 4, px1 + prompt_w + 4, py1 + prompt_h + 4], radius=24, fill=(0, 220, 255, 40))
        draw.rounded_rectangle([px1, py1, px1 + prompt_w, py1 + prompt_h], radius=20, fill=(15, 18, 28, 230), outline=(0, 220, 255, 255), width=2)
        
        draw.text((px1 + prompt_w // 2, py1 + 28), f"READY, {player_name.upper()}?", font=FONT_LABEL_BOLD, fill=(0, 220, 255, 255), anchor="mm")
        draw.text((px1 + prompt_w // 2, py1 + 68), "Press [SPACE] to Start Round", font=FONT_TITLE, fill=(255, 255, 255, 255), anchor="mm")

    elif game_state == STATE_COUNTDOWN:
        elapsed = current_time - state_start_time
        remaining = countdown_duration - elapsed
        progress = max(0.0, min(1.0, elapsed / countdown_duration))

        center_x = w // 2
        center_y = h // 2

        gauge_radius = 110
        bbox = [center_x - gauge_radius, center_y - gauge_radius, center_x + gauge_radius, center_y + gauge_radius]
        
        draw.ellipse(bbox, outline=(40, 50, 70, 180), width=10)
        start_angle = -90
        end_angle = start_angle + (360 * (1.0 - progress))
        if end_angle > start_angle:
            draw.arc(bbox, start=start_angle, end=end_angle, fill=(0, 255, 230, 255), width=10)

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

        draw.text((center_x, center_y), count_str, font=FONT_BIG_COUNT, fill=color, anchor="mm")
        draw.text((center_x, center_y + gauge_radius + 30), "SHOW GESTURE NOW!", font=FONT_LABEL_BOLD, fill=(255, 255, 255, 255), anchor="mm")

    elif game_state == STATE_SHOW_RESULT:
        card_w, card_h = 320, 200
        card_y = (h - card_h) // 2 - 20
        
        # Player Card
        p_card_x = 50
        p_color = (0, 240, 255, 255) if player_move else (255, 70, 70, 255)
        draw.rounded_rectangle([p_card_x - 3, card_y - 3, p_card_x + card_w + 3, card_y + card_h + 3], radius=18, fill=(0, 240, 255, 40))
        draw.rounded_rectangle([p_card_x, card_y, p_card_x + card_w, card_y + card_h], radius=16, fill=(12, 20, 32, 235), outline=p_color, width=2)
        
        draw.text((p_card_x + 25, card_y + 20), f"{player_name.upper()}'S MOVE", font=FONT_CARD_TITLE, fill=(0, 220, 255, 255))
        p_text = player_move if player_move else "NO GESTURE"
        draw.text((p_card_x + 25, card_y + 70), p_text, font=FONT_CARD_MOVE, fill=(255, 255, 255, 255))
        draw.text((p_card_x + 25, card_y + 135), "PLAYER 1", font=FONT_LABEL, fill=(140, 160, 190, 255))

        # AI Card
        ai_card_x = w - card_w - 50
        ai_color = (255, 60, 130, 255)
        draw.rounded_rectangle([ai_card_x - 3, card_y - 3, ai_card_x + card_w + 3, card_y + card_h + 3], radius=18, fill=(255, 60, 130, 40))
        draw.rounded_rectangle([ai_card_x, card_y, ai_card_x + card_w, card_y + card_h], radius=16, fill=(28, 12, 24, 235), outline=ai_color, width=2)
        
        draw.text((ai_card_x + 25, card_y + 20), "AI MOVE", font=FONT_CARD_TITLE, fill=(255, 80, 140, 255))
        draw.text((ai_card_x + 25, card_y + 70), ai_move if ai_move else "NONE", font=FONT_CARD_MOVE, fill=(255, 255, 255, 255))
        draw.text((ai_card_x + 25, card_y + 135), "NEURAL BOT", font=FONT_LABEL, fill=(200, 150, 180, 255))

        # Center Result Banner
        banner_w, banner_h = 440, 140
        bx = (w - banner_w) // 2
        by = (h - banner_h) // 2 - 20

        if round_result == "PLAYER":
            res_title = "VICTORY!"
            res_sub = f"+1 Point to {player_name}"
            banner_bg = (10, 45, 30, 240)
            banner_border = (0, 255, 140, 255)
            text_color = (0, 255, 160, 255)
        elif round_result == "AI":
            res_title = "AI WINS!"
            res_sub = "+1 Point to AI Bot"
            banner_bg = (45, 10, 20, 240)
            banner_border = (255, 60, 80, 255)
            text_color = (255, 75, 95, 255)
        elif round_result == "TIE":
            res_title = "DRAW MATCH!"
            res_sub = "Both chose the same move"
            banner_bg = (45, 35, 10, 240)
            banner_border = (255, 200, 0, 255)
            text_color = (255, 215, 0, 255)
        else:
            res_title = "NO DETECTION"
            res_sub = "Keep hand clear in front of camera"
            banner_bg = (35, 20, 10, 240)
            banner_border = (255, 120, 0, 255)
            text_color = (255, 140, 30, 255)

        draw.rounded_rectangle([bx - 4, by - 4, bx + banner_w + 4, by + banner_h + 4], radius=22, fill=banner_border)
        draw.rounded_rectangle([bx, by, bx + banner_w, by + banner_h], radius=20, fill=banner_bg)

        draw.text((bx + banner_w // 2, by + 45), res_title, font=FONT_BANNER, fill=text_color, anchor="mm")
        draw.text((bx + banner_w // 2, by + 95), res_sub, font=FONT_SUB_BANNER, fill=(220, 230, 240, 255), anchor="mm")

        time_left = max(0.0, result_display_duration - (current_time - state_start_time))
        bar_progress = time_left / result_display_duration
        draw.line([(bx + 20, by + banner_h - 6), (bx + 20 + int((banner_w - 40) * bar_progress), by + banner_h - 6)], fill=banner_border, width=4)

    # -------------------------------------------------------------
    # D. BOTTOM CONTROLS DOCK (Sleek Glass Dock)
    # -------------------------------------------------------------
    dock_h = 50
    dock_w = min(w - 60, 1080)
    dx1 = (w - dock_w) // 2
    dy1 = h - dock_h - 18
    dx2 = dx1 + dock_w
    dy2 = dy1 + dock_h

    draw.rounded_rectangle([dx1, dy1, dx2, dy2], radius=15, fill=(15, 17, 24, 215), outline=(50, 60, 80, 255), width=1)
    
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
        draw.text((cx - tw // 2, dy1 + 14), text, font=FONT_LABEL, fill=(210, 220, 240, 255))

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

    # Process hand landmarks
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    live_gesture = None
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            draw_cyber_hand(frame, hand_landmarks)
            live_gesture = detect_gesture(hand_landmarks)

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

    elif game_state == STATE_SHOW_RESULT:
        if current_time - state_start_time > result_display_duration:
            game_state = STATE_IDLE

    # Render Cyber UI
    display_frame = render_ui(frame, current_time, live_gesture)

    cv2.imshow(WINDOW_NAME, display_frame)

    # Key controls
    key = cv2.waitKey(20) & 0xFF

    # 1. Text input handling during Player Profile Screen
    if game_state == STATE_NAME_INPUT:
        if key == 13:  # ENTER
            chosen_name = input_text.strip() if input_text.strip() else "Player 1"
            switch_to_player(chosen_name)
            game_state = STATE_IDLE
        elif key == 27:  # ESC (Use Guest)
            switch_to_player("Guest")
            game_state = STATE_IDLE
        elif key == 8:  # BACKSPACE
            input_text = input_text[:-1]
        elif 32 <= key <= 126 and len(input_text) < 14:  # Printable character
            input_text += chr(key)
        continue

    # 2. In-Game Controls
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
    elif key == 32:  # SPACE
        if game_state == STATE_IDLE:
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
