"""Screens, drawn with Pillow. The player's card holds the live camera; the AI's card holds its hand."""
import cv2
import numpy as np
from PIL import Image, ImageDraw

import config
from ai.engine import CHOICES
from game.session import (STATE_COUNTDOWN, STATE_IDLE, STATE_NAME_INPUT,
                          STATE_SESSION_CHOICE, STATE_SHOW_RESULT, STATE_SUMMARY)
from ui.gestures import gesture_icon
from ui.theme import (FONT_BANNER, FONT_CARD_MOVE, FONT_CARD_TITLE, FONT_HISTORY, FONT_INPUT,
                      FONT_LABEL, FONT_LABEL_BOLD, FONT_MODAL_TITLE, FONT_SCORE,
                      FONT_SUB_BANNER, FONT_TITLE)

CARD_MARGIN = 30
CARD_GAP = 20
CARD_HEADER = 54
ARENA_TOP = 140
ARENA_BOTTOM_MARGIN = 85
STRIP_MIN_HEIGHT = 80

PLAYER_ACCENT = (0, 220, 255, 255)
AI_ACCENT = (255, 60, 130, 255)


def arena_layout(w, h):
    """Where the two cards, the camera panel and the move strips go on a canvas of this size."""
    card_w = (w - 2 * CARD_MARGIN - CARD_GAP) // 2
    card_y1 = ARENA_TOP
    card_y2 = h - ARENA_BOTTOM_MARGIN
    panel_w = card_w - 40
    panel_h = min(panel_w * 9 // 16, card_y2 - card_y1 - CARD_HEADER - 10 - 14 - STRIP_MIN_HEIGHT)
    panel_y1 = card_y1 + CARD_HEADER
    return {
        "card_w": card_w, "card_y1": card_y1, "card_y2": card_y2,
        "player_x1": CARD_MARGIN, "ai_x1": CARD_MARGIN + card_w + CARD_GAP,
        "panel_w": panel_w, "panel_h": panel_h, "panel_y1": panel_y1,
        "strip_y1": panel_y1 + panel_h + 10, "strip_y2": card_y2 - 14,
    }


def camera_size(w, h):
    """Size the camera picture has to be for a canvas of this size."""
    layout = arena_layout(w, h)
    return layout["panel_w"], layout["panel_h"]


EVIDENCE_COLORS = {"LOW": (255, 180, 50, 255), "MEDIUM": (0, 220, 255, 255), "HIGH": (0, 255, 150, 255)}


def _wrap(draw, text, font, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def _draw_ai_read(draw, session, x, y, width):
    """What the AI expected the player to throw, with chance marked, and why. Only shown after the reveal."""
    prediction = session.prediction
    draw.text((x, y + 26), "AI EXPECTED YOU TO THROW", font=FONT_LABEL_BOLD, fill=(255, 120, 170, 255), anchor="lm")
    if prediction.expected is None:
        draw.text((x, y + 70), "NO PATTERN YET", font=FONT_CARD_TITLE, fill=(180, 140, 170, 255), anchor="lm")
        evidence_y = y + 112
        text_y = y + 140
    else:
        bar_x = x + 92
        bar_w = width - 92 - 50
        for i, move in enumerate(CHOICES):
            row_y = y + 62 + i * 38
            probability = prediction.probs[move]
            thrown = move == session.player_move
            draw.text((x, row_y), move, font=FONT_LABEL_BOLD, fill=PLAYER_ACCENT if thrown else (225, 215, 235, 255), anchor="lm")
            draw.rounded_rectangle([bar_x, row_y - 8, bar_x + bar_w, row_y + 8], radius=6, fill=(30, 18, 32, 255),
                                   outline=PLAYER_ACCENT if thrown else None, width=2)
            draw.rounded_rectangle([bar_x, row_y - 8, bar_x + max(12, int(bar_w * probability)), row_y + 8], radius=6,
                                   fill=(255, 70, 140, 255) if move == prediction.expected else (150, 60, 100, 255))
            chance_x = bar_x + bar_w // 3
            draw.line([(chance_x, row_y - 12), (chance_x, row_y + 12)], fill=(255, 255, 255, 210), width=1)
            draw.text((bar_x + bar_w + 10, row_y), f"{round(probability * 100)}%", font=FONT_LABEL, fill=(235, 225, 240, 255), anchor="lm")
        evidence_y = y + 172
        text_y = y + 198
        draw.text((x + width, evidence_y), "white tick = chance", font=FONT_HISTORY, fill=(150, 140, 165, 255), anchor="rm")
    draw.text((x, evidence_y), f"EVIDENCE: {prediction.evidence}", font=FONT_LABEL_BOLD,
              fill=EVIDENCE_COLORS[prediction.evidence], anchor="lm")
    for j, line in enumerate(_wrap(draw, session.explanation, FONT_LABEL, width)[:5]):
        draw.text((x, text_y + j * 21), line, font=FONT_LABEL, fill=(235, 220, 235, 255))


def _draw_summary(draw, session, w, h):
    """The end-of-match screen: the score, how well the AI read the player, and the habit it found."""
    summary = session.summary
    draw.text((w // 2, 50), "ROCK PAPER SCISSORS AI", font=FONT_BANNER, fill=(35, 55, 90, 180), anchor="mm")
    modal_w, modal_h = 780, 560
    mx1, my1 = (w - modal_w) // 2, (h - modal_h) // 2 + 16
    mx2, my2 = mx1 + modal_w, my1 + modal_h
    draw.rounded_rectangle([mx1 - 4, my1 - 4, mx2 + 4, my2 + 4], radius=24, fill=(0, 240, 255, 60))
    draw.rounded_rectangle([mx1, my1, mx2, my2], radius=20, fill=(15, 18, 28, 250), outline=PLAYER_ACCENT, width=2)
    cx = w // 2

    colors = {"YOU WIN": (0, 255, 160, 255), "AI WINS": (255, 75, 95, 255), "DRAW": (255, 215, 0, 255)}
    draw.text((cx, my1 + 34), f"MATCH COMPLETE  -  {session.player_name.upper()}", font=FONT_CARD_TITLE, fill=(160, 180, 210, 255), anchor="mm")
    draw.text((cx, my1 + 84), summary.headline, font=FONT_BANNER, fill=colors[summary.headline], anchor="mm")
    draw.text((cx, my1 + 132), f"YOU {summary.wins}     AI {summary.losses}     DRAWS {summary.ties}", font=FONT_TITLE, fill=(255, 255, 255, 255), anchor="mm")
    draw.line([(mx1 + 40, my1 + 160), (mx2 - 40, my1 + 160)], fill=(50, 60, 80, 255), width=1)

    draw.text((cx, my1 + 188), "WHAT THE AI LEARNED ABOUT YOU", font=FONT_LABEL_BOLD, fill=(255, 120, 170, 255), anchor="mm")
    if summary.predicted_rounds:
        line = (f"It predicted {summary.hits} of {summary.predicted_rounds} of your throws "
                f"({round(summary.accuracy * 100)}%). Guessing blindly gets about 33%.")
    else:
        line = "It never had enough to make a prediction."
    draw.text((cx, my1 + 220), line, font=FONT_SUB_BANNER, fill=(235, 235, 245, 255), anchor="mm")

    # Running accuracy as the match went on, with chance marked
    gx1, gy1, gx2, gy2 = mx1 + 70, my1 + 252, mx2 - 70, my1 + 372
    draw.rounded_rectangle([gx1 - 12, gy1 - 12, gx2 + 12, gy2 + 12], radius=10, fill=(20, 26, 40, 255))
    chance_y = gy2 - int((gy2 - gy1) / 3)
    for dash in range(gx1, gx2, 14):
        draw.line([(dash, chance_y), (dash + 7, chance_y)], fill=(255, 255, 255, 140), width=1)
    draw.text((gx2 - 2, chance_y - 10), "chance", font=FONT_HISTORY, fill=(170, 180, 200, 255), anchor="rm")
    draw.text((gx1 - 18, gy1), "100%", font=FONT_HISTORY, fill=(130, 145, 170, 255), anchor="rm")
    draw.text((gx1 - 18, gy2), "0%", font=FONT_HISTORY, fill=(130, 145, 170, 255), anchor="rm")
    count = len(summary.running_accuracy)
    points = [((gx1 + int(i * (gx2 - gx1) / (count - 1))) if count > 1 else (gx1 + gx2) // 2,
               gy2 - int((gy2 - gy1) * acc)) for i, acc in enumerate(summary.running_accuracy)]
    if len(points) > 1:
        draw.line(points, fill=(255, 120, 170, 255), width=3)
    for point, hit in zip(points, summary.hit_flags):
        draw.ellipse([point[0] - 6, point[1] - 6, point[0] + 6, point[1] + 6],
                     fill=(0, 255, 160, 255) if hit else (255, 75, 95, 255))
    draw.text((cx, gy2 + 26), "green = the AI guessed that throw, red = it missed", font=FONT_HISTORY, fill=(150, 160, 180, 255), anchor="mm")

    for j, habit_line in enumerate(_wrap(draw, summary.habit, FONT_SUB_BANNER, modal_w - 120)[:2]):
        draw.text((cx, my1 + 424 + j * 26), habit_line, font=FONT_SUB_BANNER, fill=PLAYER_ACCENT, anchor="mm")
    draw.text((cx, my1 + 520), "[SPACE] New match      [P] Switch player      [Q] Quit", font=FONT_LABEL_BOLD, fill=(255, 200, 0, 255), anchor="mm")


_mask_cache = {}

def _rounded_mask(w, h, radius):
    if (w, h, radius) not in _mask_cache:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
        _mask_cache[(w, h, radius)] = mask
    return _mask_cache[(w, h, radius)]


def _card_frame(draw, x1, y1, x2, y2, accent, glow, fill):
    draw.rounded_rectangle([x1 - 2, y1 - 2, x2 + 2, y2 + 2], radius=18, fill=glow)
    draw.rounded_rectangle([x1, y1, x2, y2], radius=16, fill=fill, outline=accent, width=2)


def _pill(draw, cx, cy, text, font, color, pad=16, height=34):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    half_w = (right - left) // 2 + pad
    draw.rounded_rectangle([cx - half_w, cy - height // 2, cx + half_w, cy + height // 2], radius=height // 2,
                           fill=(15, 18, 28, 220), outline=color, width=1)
    draw.text((cx, cy), text, font=font, fill=color, anchor="mm")


def _status(draw, right, cy, text, color):
    """A dot and a short status, right-aligned."""
    left, top, text_right, bottom = draw.textbbox((0, 0), text, font=FONT_LABEL_BOLD)
    draw.text((right, cy), text, font=FONT_LABEL_BOLD, fill=color, anchor="rm")
    dot_x = right - (text_right - left) - 22
    draw.ellipse([dot_x, cy - 5, dot_x + 10, cy + 5], fill=color)


def _move_strip(overlay, draw, x1, y1, x2, y2, active, accent, active_fill):
    """Rock, paper and scissors side by side, with the chosen one lit."""
    gap = 14
    tile_w = (x2 - x1 - 2 * gap) // 3
    for i, move in enumerate(CHOICES):
        tx1 = x1 + i * (tile_w + gap)
        tx2 = tx1 + tile_w
        lit = move == active
        draw.rounded_rectangle([tx1, y1, tx2, y2], radius=14, fill=active_fill if lit else (20, 28, 44, 220),
                               outline=accent if lit else (45, 60, 85, 255), width=3 if lit else 1)
        icon = gesture_icon(move, y2 - y1 - 10, opacity=1.0 if lit else (0.55 if active is None else 0.28))
        if icon is not None:
            overlay.alpha_composite(icon, (tx1 + (tile_w - icon.width) // 2, y1 + 6))
        else:
            draw.text(((tx1 + tx2) // 2, (y1 + y2) // 2), move, font=FONT_LABEL_BOLD,
                      fill=accent if lit else (120, 140, 170, 255), anchor="mm")


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

def render_ui(session, w, h, current_time, live_gesture, view):

    # Dark arena background with grid, rendered once per resolution and reused
    pil_frame = get_background(w, h).copy()
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # -------------------------------------------------------------
    # STATE 1: NAME INPUT PROFILE SCREEN
    # -------------------------------------------------------------
    if session.state == STATE_NAME_INPUT:
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
        display_name = (session.input_text if session.input_text else "Enter Name...") + cursor
        text_color = (0, 255, 220, 255) if session.input_text else (120, 140, 170, 255)
        draw.text((ib_x1 + 20, ib_y1 + 16), display_name, font=FONT_INPUT, fill=text_color)

        draw.text((mx1 + modal_w // 2, my1 + 225), "Press [ENTER] to Confirm   |   [ESC] Use Guest", font=FONT_LABEL_BOLD, fill=(255, 200, 0, 255), anchor="mm")

        final_img = Image.alpha_composite(pil_frame, overlay)
        return cv2.cvtColor(np.array(final_img.convert("RGB")), cv2.COLOR_RGB2BGR)

    # -------------------------------------------------------------
    # STATE 2: RETURNING PLAYER SESSION CHOICE SCREEN
    # -------------------------------------------------------------
    elif session.state == STATE_SESSION_CHOICE:
        draw.text((w // 2, 70), "ROCK PAPER SCISSORS AI", font=FONT_BANNER, fill=(35, 55, 90, 180), anchor="mm")

        modal_w, modal_h = 680, 340
        mx1 = (w - modal_w) // 2
        my1 = (h - modal_h) // 2
        mx2 = mx1 + modal_w
        my2 = my1 + modal_h

        draw.rounded_rectangle([mx1 - 4, my1 - 4, mx2 + 4, my2 + 4], radius=24, fill=(0, 240, 255, 70))
        draw.rounded_rectangle([mx1, my1, mx2, my2], radius=20, fill=(15, 18, 28, 250), outline=(0, 240, 255, 255), width=2)

        draw.text((mx1 + modal_w // 2, my1 + 35), f"WELCOME BACK, {session.temp_player_name.upper()}!", font=FONT_MODAL_TITLE, fill=(0, 240, 255, 255), anchor="mm")
        
        stats_text = f"Previous Session: YOU {session.prev_score_player}  |  AI {session.prev_score_ai}  |  TIES {session.prev_score_ties}   (Best Streak: {session.prev_best_streak})"
        draw.text((mx1 + modal_w // 2, my1 + 75), stats_text, font=FONT_LABEL, fill=(200, 215, 240, 255), anchor="mm")

        b1_x1, b1_y1, b1_x2, b1_y2 = mx1 + 40, my1 + 115, mx2 - 40, my1 + 185
        draw.rounded_rectangle([b1_x1, b1_y1, b1_x2, b1_y2], radius=14, fill=(15, 45, 60, 240), outline=(0, 230, 255, 255), width=2)
        draw.text((b1_x1 + 25, b1_y1 + 14), "[ENTER] or [N]  START NEW GAME", font=FONT_LABEL_BOLD, fill=(0, 255, 220, 255))
        draw.text((b1_x1 + 25, b1_y1 + 42), "Reset scores to 0-0  (Keeps AI learned habits & best session.streak record)", font=FONT_LABEL, fill=(180, 210, 230, 255))

        b2_x1, b2_y1, b2_x2, b2_y2 = mx1 + 40, my1 + 205, mx2 - 40, my1 + 275
        draw.rounded_rectangle([b2_x1, b2_y1, b2_x2, b2_y2], radius=14, fill=(45, 20, 45, 240), outline=(240, 80, 220, 255), width=2)
        draw.text((b2_x1 + 25, b2_y1 + 14), "[C]  CONTINUE / RESUME SCORES", font=FONT_LABEL_BOLD, fill=(255, 120, 240, 255))
        draw.text((b2_x1 + 25, b2_y1 + 42), f"Resume previous scores (YOU: {session.prev_score_player} | AI: {session.prev_score_ai} | TIES: {session.prev_score_ties})", font=FONT_LABEL, fill=(220, 190, 220, 255))

        draw.text((mx1 + modal_w // 2, my1 + 305), "Press [ESC] to change name", font=FONT_LABEL, fill=(140, 150, 175, 255), anchor="mm")

        final_img = Image.alpha_composite(pil_frame, overlay)
        return cv2.cvtColor(np.array(final_img.convert("RGB")), cv2.COLOR_RGB2BGR)

    elif session.state == STATE_SUMMARY:
        _draw_summary(draw, session, w, h)
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
    draw.text((bar_x1 + 25, bar_y1 + 16), f"PLAYER: {session.player_name.upper()}", font=FONT_TITLE, fill=(255, 255, 255, 255))
    
    mode_color = (0, 230, 180, 255) if session.engine.mode == "Predictive" else (220, 220, 220, 255)
    ai_tag = f"AI: {session.engine.mode.upper()} [D to toggle]"
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
    draw.text((center_x - 85, bar_y1 + 28), str(session.score_player), font=FONT_SCORE, fill=(255, 255, 255, 255))

    draw.text((center_x - 20, bar_y1 + 38), "VS", font=FONT_LABEL_BOLD, fill=(140, 150, 180, 255))
    if config.MATCH_ROUNDS > 0:
        played = len(session.match_log)
        shown_round = played if session.state == STATE_SHOW_RESULT and played else min(played + 1, config.MATCH_ROUNDS)
        draw.text((center_x, bar_y1 + 72), f"{shown_round}/{config.MATCH_ROUNDS}", font=FONT_HISTORY,
                  fill=(140, 150, 180, 255), anchor="mm")

    draw.rounded_rectangle([center_x + 45, bar_y1 + 20, center_x + 170, bar_y1 + 86], radius=12, fill=(65, 15, 35, 230), outline=(255, 60, 110, 255), width=2)
    draw.text((center_x + 58, bar_y1 + 24), "AI", font=FONT_LABEL_BOLD, fill=(255, 80, 130, 255))
    draw.text((center_x + 130, bar_y1 + 28), str(session.score_ai), font=FONT_SCORE, fill=(255, 255, 255, 255))

    # Right: Streak & Match History Pills
    streak_str = f"STREAK: {session.streak}  (Best: {session.best_streak})"
    s_left, s_top, s_right, s_bottom = draw.textbbox((0, 0), streak_str, font=FONT_LABEL_BOLD)
    s_w = (s_right - s_left) + 45
    s_x2 = bar_x2 - 25
    s_x1 = s_x2 - s_w
    s_y1 = bar_y1 + 16
    s_y2 = s_y1 + 32

    streak_bg = (60, 42, 10, 240) if session.streak > 0 else (25, 28, 38, 220)
    streak_border = (255, 190, 0, 255) if session.streak > 0 else (55, 65, 85, 255)
    draw.rounded_rectangle([s_x1, s_y1, s_x2, s_y2], radius=10, fill=streak_bg, outline=streak_border, width=1)
    
    star_col = (255, 210, 50, 255) if session.streak > 0 else (120, 130, 150, 255)
    draw.ellipse([s_x1 + 12, s_y1 + 11, s_x1 + 22, s_y1 + 21], fill=star_col)
    draw.text((s_x1 + 28, s_y1 + 4), streak_str, font=FONT_LABEL_BOLD, fill=star_col)

    # History Pills
    draw.text((s_x2 - 210, bar_y1 + 68), "RECENT:", font=FONT_LABEL, fill=(140, 150, 175, 255), anchor="lm")
    hx = s_x2 - 130
    badge_size = 22
    by = bar_y1 + 57
    for res in session.match_history:
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
    # B. ARENA: PLAYER CARD (live camera) | AI CARD (its hand)
    # -------------------------------------------------------------
    lay = arena_layout(w, h)
    cam_w, cam_h = lay["panel_w"], lay["panel_h"]
    card_y1, card_y2 = lay["card_y1"], lay["card_y2"]
    px1 = lay["player_x1"]
    px2 = px1 + lay["card_w"]
    ax1 = lay["ai_x1"]
    ax2 = ax1 + lay["card_w"]
    cam_x, cam_y = px1 + 20, lay["panel_y1"]
    ai_panel_x = ax1 + 20
    header_y = card_y1 + 30

    # 1. Player card
    _card_frame(draw, px1, card_y1, px2, card_y2, PLAYER_ACCENT, (0, 240, 255, 30), (15, 22, 34, 245))
    draw.text((px1 + 24, header_y), "YOUR ACTION", font=FONT_CARD_TITLE, fill=PLAYER_ACCENT, anchor="lm")

    if session.state == STATE_SHOW_RESULT:
        shown_move = session.player_move
        status_text = f"FINAL MOVE: {shown_move}" if shown_move else "NO MOVE"
        status_col = (0, 255, 180, 255) if shown_move else (255, 70, 70, 255)
    else:
        shown_move = live_gesture
        status_text = f"DETECTED: {live_gesture}" if live_gesture else "SEARCHING..."
        status_col = (0, 255, 150, 255) if live_gesture else (255, 180, 50, 255)
    _status(draw, px2 - 24, header_y, status_text, status_col)

    cam_pil = Image.fromarray(cv2.cvtColor(view.image, cv2.COLOR_BGR2RGB)).convert("RGBA")
    overlay.paste(cam_pil, (cam_x, cam_y), _rounded_mask(cam_w, cam_h, 14))
    draw.rounded_rectangle([cam_x, cam_y, cam_x + cam_w, cam_y + cam_h], radius=14, outline=(0, 220, 255, 200), width=2)

    if session.state == STATE_COUNTDOWN:
        _pill(draw, cam_x + cam_w // 2, cam_y + 28, "SHOW GESTURE NOW!", FONT_LABEL_BOLD, (255, 255, 255, 255))
    elif not view.hand_found and session.state != STATE_SHOW_RESULT:
        _pill(draw, cam_x + cam_w // 2, cam_y + 28, "SHOW YOUR HAND", FONT_LABEL_BOLD, (255, 180, 50, 255))
    if session.state == STATE_IDLE:
        _pill(draw, cam_x + cam_w // 2, cam_y + cam_h - 34, "ARE YOU READY?   Press [SPACE] to Start",
              FONT_LABEL_BOLD, PLAYER_ACCENT, pad=22, height=40)

    _move_strip(overlay, draw, cam_x, lay["strip_y1"], cam_x + cam_w, lay["strip_y2"],
                shown_move, PLAYER_ACCENT, (10, 45, 65, 235))

    # 2. AI card
    _card_frame(draw, ax1, card_y1, ax2, card_y2, AI_ACCENT, (255, 60, 130, 30), (32, 14, 26, 245))
    draw.text((ax1 + 24, header_y), "AI OPPONENT", font=FONT_CARD_TITLE, fill=(255, 80, 140, 255), anchor="lm")
    draw.text((ax2 - 24, header_y), f"MARKOV AI ({session.engine.mode.upper()})", font=FONT_LABEL,
              fill=(220, 160, 190, 255), anchor="rm")

    draw.rounded_rectangle([ai_panel_x, cam_y, ai_panel_x + cam_w, cam_y + cam_h], radius=14,
                           fill=(40, 16, 34, 255), outline=(110, 50, 85, 255), width=2)
    ai_cx = ai_panel_x + cam_w // 2
    ai_cy = cam_y + cam_h // 2

    if session.state == STATE_SHOW_RESULT and session.ai_move:
        # The AI hand hangs down from the top edge on the left; what it expected is on the right
        hand_cx = ai_panel_x + 112
        icon = gesture_icon(session.ai_move, cam_h - 8, upside_down=True)
        if icon is not None:
            overlay.alpha_composite(icon, (hand_cx - icon.width // 2, cam_y + 4))
        else:
            draw.text((hand_cx, ai_cy), session.ai_move, font=FONT_CARD_MOVE, fill=(255, 100, 160, 255), anchor="mm")
        _draw_ai_read(draw, session, ai_panel_x + 236, cam_y, cam_w - 250)
    elif session.state == STATE_COUNTDOWN:
        # The dots are drawn after the word, with room kept for all three so the word never shifts
        dots = "." * (int(current_time * 3) % 4)
        word_w = draw.textlength("DECIDING", font=FONT_CARD_MOVE)
        start_x = ai_cx - (word_w + draw.textlength("...", font=FONT_CARD_MOVE)) / 2
        draw.text((start_x, ai_cy - 14), "DECIDING", font=FONT_CARD_MOVE, fill=(255, 180, 80, 255), anchor="lm")
        draw.text((start_x + word_w + 2, ai_cy - 14), dots, font=FONT_CARD_MOVE, fill=(255, 180, 80, 255), anchor="lm")
        draw.text((ai_cx, ai_cy + 28), "MOVE LOCKED", font=FONT_LABEL_BOLD, fill=(230, 180, 210, 255), anchor="mm")
        evidence = session.prediction.evidence
        draw.text((ai_cx, ai_cy + 58), f"EVIDENCE: {evidence}", font=FONT_LABEL, fill=EVIDENCE_COLORS[evidence], anchor="mm")
    else:
        draw.text((ai_cx, ai_cy - 14), "READY", font=FONT_CARD_MOVE, fill=(180, 140, 170, 255), anchor="mm")
        draw.text((ai_cx, ai_cy + 28), "AWAITING ROUND", font=FONT_LABEL_BOLD, fill=(230, 180, 210, 255), anchor="mm")
        if session.engine.rounds_seen:
            draw.text((ai_cx, ai_cy + 58), f"It has seen {session.engine.rounds_seen} of your throws", font=FONT_LABEL,
                      fill=(190, 160, 180, 255), anchor="mm")

    _move_strip(overlay, draw, ai_panel_x, lay["strip_y1"], ai_panel_x + cam_w, lay["strip_y2"],
                session.ai_move if session.state == STATE_SHOW_RESULT else None, AI_ACCENT, (65, 15, 35, 235))

    # -------------------------------------------------------------
    # C. COUNTDOWN RING AND RESULT BANNER
    # -------------------------------------------------------------
    if session.state == STATE_COUNTDOWN:
        elapsed = current_time - session.state_start_time
        remaining = session.countdown_duration - elapsed
        progress = max(0.0, min(1.0, elapsed / session.countdown_duration))

        # The ring replaces "VS" in the scoreboard bar
        c_cx = w // 2
        c_cy = 71

        gauge_r = 34
        bbox = [c_cx - gauge_r, c_cy - gauge_r, c_cx + gauge_r, c_cy + gauge_r]

        draw.ellipse(bbox, fill=(15, 17, 24, 255), outline=(40, 50, 70, 200), width=5)
        start_angle = -90
        end_angle = start_angle + (360 * (1.0 - progress))
        if end_angle > start_angle:
            draw.arc(bbox, start=start_angle, end=end_angle, fill=(0, 255, 230, 255), width=5)

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

        draw.text((c_cx, c_cy), count_str, font=FONT_CARD_MOVE, fill=color, anchor="mm")

    elif session.state == STATE_SHOW_RESULT:
        # The banner sits at the bottom of the camera panel, so it never covers the AI's hand
        banner_w, banner_h = 400, 84
        bx = cam_x + (cam_w - banner_w) // 2
        by = cam_y + cam_h - banner_h - 14

        if session.round_result == "PLAYER":
            res_title = "VICTORY!"
            res_sub = f"+1 Point to {session.player_name.upper()}"
            banner_bg = (10, 45, 30, 245)
            banner_border = (0, 255, 140, 255)
            text_color = (0, 255, 160, 255)
        elif session.round_result == "AI":
            res_title = "AI WINS!"
            res_sub = "+1 Point to AI Bot"
            banner_bg = (45, 10, 20, 245)
            banner_border = (255, 60, 80, 255)
            text_color = (255, 75, 95, 255)
        elif session.round_result == "TIE":
            res_title = "DRAW MATCH!"
            res_sub = "Both chose the same move"
            banner_bg = (45, 35, 10, 245)
            banner_border = (255, 200, 0, 255)
            text_color = (255, 215, 0, 255)
        else:
            res_title = "NO DETECTION"
            res_sub = "Keep your hand in view"
            banner_bg = (35, 20, 10, 245)
            banner_border = (255, 120, 0, 255)
            text_color = (255, 140, 30, 255)

        draw.rounded_rectangle([bx - 3, by - 3, bx + banner_w + 3, by + banner_h + 3], radius=20, fill=banner_border)
        draw.rounded_rectangle([bx, by, bx + banner_w, by + banner_h], radius=18, fill=banner_bg)

        draw.text((bx + banner_w // 2, by + 28), res_title, font=FONT_BANNER, fill=text_color, anchor="mm")
        draw.text((bx + banner_w // 2, by + 64), res_sub, font=FONT_SUB_BANNER, fill=(220, 230, 240, 255), anchor="mm")

        prompt = "Press [SPACE] to see your match summary" if session.match_complete else "Press [SPACE] for Next Round"
        _pill(draw, cam_x + cam_w // 2, cam_y + 28, prompt, FONT_LABEL_BOLD, (0, 255, 220, 255), pad=22, height=38)

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
