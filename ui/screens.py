"""Every screen, drawn with Pillow on a 1280 x 720 design that is scaled to the camera frame size.

You are on the left (teal), the AI is on the right (red), and the match happens in the middle.
"""
import math

import cv2
import numpy as np
from PIL import Image

import config
from ai.engine import CHOICES
from game.session import (STATE_CAMERA_CHECK, STATE_COUNTDOWN, STATE_IDLE, STATE_NAME_INPUT, STATE_REPLAY,
                          STATE_SHOW_RESULT, STATE_START, STATE_SUMMARY)
from game.summary import TITLES, title_index
from ui import theme
from ui import canvas as canvas_module
from ui.canvas import Canvas, Layout, aa_mask, draw_card, make_background
from ui.gestures import gesture_icon

# Where things sit in the design (1280 x 720)
CARD_TOP, CARD_H = 70, 520                 # the two player cards and the middle card share this top and height
MATCH_CAM = (44, CARD_TOP + 62, 408, 430)   # your camera picture
AI_PANEL = (828, CARD_TOP + 62, 408, 430)   # the AI's hand
LEARN_BOX = (828, CARD_TOP + 62 + 430 - 146, 408, 146)
CHECK_CAM = (60, 156, 640, 440)
ROCK_SCALE = 0.84   # the rock artwork is bigger than the others, so it is drawn smaller to match

_backgrounds = {}
_static = {}
_layouts = {}


def _layout(w, h):
    if (w, h) not in _layouts:
        _layouts[(w, h)] = Layout(w, h)
    return _layouts[(w, h)]


def camera_size(state, w, h):
    """Size the camera picture has to be for this screen and frame size."""
    x, y, pw, ph = CHECK_CAM if state == STATE_CAMERA_CHECK else MATCH_CAM
    x1, y1, x2, y2 = _layout(w, h).box(x, y, pw, ph)
    return x2 - x1, y2 - y1


def clear_caches():
    """Forget everything drawn for the old frame size, e.g. after the window is resized."""
    for cache in (_backgrounds, _static, _layouts, _hand_cards):
        cache.clear()
    canvas_module.clear_caches()


def _begin(L, key, build=None):
    """A canvas on a copy of the background, plus anything `build` drew once (cards and their shadows)."""
    cache_key = (L.w, L.h, key)
    if cache_key not in _static:
        if (L.w, L.h) not in _backgrounds:
            _backgrounds[(L.w, L.h)] = make_background(L)
        image = _backgrounds[(L.w, L.h)].copy()
        if build:
            build(Canvas(image, L))
        _static[cache_key] = image
    return Canvas(_static[cache_key].copy(), L)


def _bgr(canvas):
    return cv2.cvtColor(np.asarray(canvas.img), cv2.COLOR_RGB2BGR)


# ---------------------------------------------------------------- small parts
def _keycap(c, x, cy, label, size=13, fill=theme.CARD):
    """A keyboard key with its label, left edge at x. Returns the right edge."""
    w = max(26, c.tw(label, size, True) + 16)
    c.rect(x, cy - 12, w, 24, fill=theme.KEY_LINE, radius=8)
    c.rect(x, cy - 12, w, 21, fill=fill, radius=8)
    c.text(x + w / 2, cy - 1, label, size, theme.INK, True, "mm")
    return x + w


def _hints(c, items, y=678):
    widths = [max(26, c.tw(k, 13, True) + 16) + 6 + c.tw(label, 15) for k, label in items]
    x = 640 - (sum(widths) + 26 * (len(items) - 1)) / 2
    for (key, label), width in zip(items, widths):
        edge = _keycap(c, x, y, key)
        c.text(edge + 6, y, label, 15, theme.MUTED)
        x += width + 26


def _chip(c, right, cy, text, fg, bg, dot=True):
    width = c.tw(text, 14, True) + 26 + (16 if dot else 0)
    x = right - width
    c.rect(x, cy - 15, width, 30, fill=bg, radius=15)
    if dot:
        c.circle(x + 18, cy, 4.5, fill=fg)
    c.text(x + (30 if dot else 13), cy, text, 14, fg, True)


def _pill(c, cx, cy, text, colour, size=15):
    width = c.tw(text, size, True) + 32
    c.rect(cx - width / 2 - 1, cy - 17, width + 2, 34, fill=colour, radius=17)
    c.rect(cx - width / 2, cy - 16, width, 32, fill=theme.WHITE, radius=16)
    c.text(cx, cy, text, size, colour, True, "mm")


def _tile(c, x, y, w, h, move, side, lit, dim=False, hanging=False):
    """A dark tile with a hand picture. `lit` tiles get a coloured border; the rest are faded."""
    accent, fill = (theme.PLAYER, theme.TILE_PLAYER) if side == "p" else (theme.AI, theme.TILE_AI)
    if lit:
        c.rect(x, y, w, h, fill=accent, radius=14)
        c.rect(x + 3, y + 3, w - 6, h - 6, fill=fill, radius=11)
    else:
        c.rect(x, y, w, h, fill=theme.TILE_LINE, radius=14)
        c.rect(x + 1, y + 1, w - 2, h - 2, fill=theme.TILE, radius=13)
    height = c.L.d(h - 10)
    shown = round(height * ROCK_SCALE) if move == "ROCK" else height
    icon = gesture_icon(move, shown, opacity=1.0 if lit else (0.34 if dim else 0.62), upside_down=hanging)
    if icon is not None:
        # Upright hands rise from the bottom of the tile, hanging ones from the top
        c.paste_centered(icon, x + w / 2, y + 2 + (0 if hanging else 4 + (height - shown) / c.L.s))
    else:
        c.text(x + w / 2, y + h / 2, move[0], 28, theme.WHITE if lit else theme.FAINT, True, "mm")


def _trophy(c, cx, cy, size, colour):
    k = size / 24
    ox, oy = cx - 12 * k, cy - 12 * k
    p = lambda px, py: (ox + px * k, oy + py * k)
    for sign in (-1, 1):  # handles
        pts = [p(12 + sign * 5, 5), p(12 + sign * 8.5, 5), p(12 + sign * 8.5, 8), p(12 + sign * 5, 10.5)]
        c.line(pts, colour, 1.8 * k)
    c.rect(ox + 7 * k, oy + 3 * k, 10 * k, 5.5 * k, fill=colour)
    c.pie(ox + 12 * k, oy + 8.5 * k, 5 * k, 0, 180, colour)
    c.rect(ox + 11 * k, oy + 12.5 * k, 2 * k, 4.5 * k, fill=colour)
    c.rect(ox + 7.5 * k, oy + 17 * k, 9 * k, 3.2 * k, fill=colour, radius=1.2 * k)


def _check(c, cx, cy, r=18):
    c.circle(cx, cy, r, fill=theme.GREEN)
    k = r / 18
    c.line([(cx - 7 * k, cy), (cx - 2 * k, cy + 6 * k), (cx + 8 * k, cy - 6 * k)], theme.WHITE, 3.4 * k)


def _spinner(c, cx, cy, now, r=16):
    c.circle(cx, cy, r, outline=theme.TRACK, width=4)
    start = (now * 330) % 360
    c.arc(cx, cy, r, start, start + 90, theme.AMBER, 4)


def _hold_ring(c, x, y, w, h, progress):
    cx, cy, r = x + w / 2, y + h * 0.56, min(w, h) * 0.36
    c.circle(cx, cy, r, outline=(236, 232, 232), width=10)
    if progress > 0:
        c.arc(cx, cy, r, -90, -90 + 360 * progress, theme.PLAYER, 10)


def _camera(c, view, rect, placeholder="No camera picture"):
    x, y, w, h = rect
    if view is None:
        c.rect(x, y, w, h, fill=theme.TILE, radius=16)
        c.text(x + w / 2, y + h / 2, placeholder, 18, theme.FAINT, False, "mm")
        return
    c.paste_rounded(Image.fromarray(cv2.cvtColor(view.image, cv2.COLOR_BGR2RGB)), x, y, w, h, 16)


def _gradient(L, w, h, top, bottom):
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    rows = np.array(top, np.float32) * (1 - t) + np.array(bottom, np.float32) * t
    return Image.fromarray(np.broadcast_to(rows, (h, w, 3)).astype(np.uint8), "RGB")


def _dim(c, strength=0.45):
    c.img.paste(Image.blend(c.img, Image.new("RGB", c.img.size, (20, 30, 50)), strength))


# ---------------------------------------------------------------- 1. start screen
_HAND_GRADIENTS = {"ROCK": ((59, 79, 216), (23, 30, 90)), "PAPER": ((71, 85, 105), (15, 23, 42)),
                   "SCISSORS": ((244, 63, 94), (96, 18, 40))}
_hand_cards = {}


def _hand_card(L, move, angle):
    """A tilted hand card. Built three times too big, then shrunk, so the tilted edges come out smooth."""
    key = (L.w, L.h, move)
    if key not in _hand_cards:
        ss = 3
        w, h = L.d(156) * ss, L.d(200) * ss
        card = _gradient(L, w, h, *_HAND_GRADIENTS[move]).convert("RGBA")
        icon = gesture_icon(move, L.d(142 if move == "ROCK" else 184) * ss)
        if icon is not None:
            card.alpha_composite(icon, ((w - icon.width) // 2, h - icon.height + L.d(6) * ss))
        card.putalpha(aa_mask(w, h, L.d(22) * ss))
        big = card.rotate(angle, resample=Image.BICUBIC, expand=True)
        _hand_cards[key] = big.resize((big.width // ss, big.height // ss), Image.LANCZOS)
    return _hand_cards[key]


def _build_start(c):
    draw_card(c, 740, 40, 500, 640, accent=theme.AMBER)


def _start(session, L, now):
    c = _begin(L, "start", _build_start)
    dy = 64   # the title, hands and button are centred on the screen
    c.runs(390, 96 + dy, [("ROCK PAPER SCISSORS ", theme.INK), ("AI", theme.PLAYER)], 44)
    c.text(390, 142 + dy, "An AI that learns your habits. Can you beat it?", 19, theme.MUTED, False, "mm")
    for move, cx, angle, delay in (("ROCK", 215, 5, 0), ("PAPER", 390, 0, 0.5), ("SCISSORS", 565, -5, 1.0)):
        lift = 12 * (0.5 - 0.5 * math.cos(2 * math.pi * (now + delay) / 3.4))
        card = _hand_card(L, move, angle)
        c.img.paste(card, (L.x(cx) - card.width // 2, L.y(296 + dy - lift) - card.height // 2), card)

    c.rect(214, 435 + dy, 352, 54, fill=theme.PLAYER, radius=27)
    parts = [("PRESS", None), ("SPACE", "key"), ("TO PLAY", None)]
    widths = [c.tw(t, 26, True) if k is None else max(26, c.tw(t, 13, True) + 16) for t, k in parts]
    x = 390 - (sum(widths) + 24) / 2
    for (text, kind), width in zip(parts, widths):
        if kind is None:
            c.text(x, 462 + dy, text, 26, theme.WHITE, True)
        else:
            c.rect(x, 450 + dy, width, 24, fill=theme.WHITE, radius=8)
            c.text(x + width / 2, 462 + dy, text, 13, theme.PLAYER_D, True, "mm")
        x += width + 12
    c.text(390, 512 + dy, "Beat the AI to climb the leaderboard", 15, theme.MUTED, False, "mm")
    c.text(390, 664, "Your hand is tracked live on this computer. No video is saved.", 13, theme.FAINT, False, "mm")

    # Leaderboard
    c.text(768, 84, "LEADERBOARD", 26, theme.INK, True)
    c.text(768, 112, "Who beat the AI most · best score in a match", 13.5, theme.MUTED)
    c.spaced(782, 146, "#", 11, theme.FAINT, spacing=2, anchor="l")
    c.spaced(840, 146, "PLAYER", 11, theme.FAINT, spacing=2, anchor="l")
    c.spaced(1208, 146, "WON – LOST", 11, theme.FAINT, spacing=2, anchor="rm")
    rows = session.leaderboard_rows
    for i, (name, best) in enumerate(rows):
        y = 162 + i * 57
        top = i == 0
        if top:
            c.rect(756, y, 468, 50, fill=theme.AMBER, radius=14)
            c.rect(758, y + 2, 464, 46, fill=theme.AMBER_T, radius=12)
        else:
            c.rect(756, y, 468, 50, fill=theme.ROW, radius=14)
        if i < 3:
            _trophy(c, 784, y + 25, 40, theme.MEDALS[i])
        else:
            c.text(785, y + 26, str(i + 1), 19, theme.FAINT, True, "mm")
        c.text(840, y + 26, name.upper(), 21, theme.INK, True)
        c.text(1204, y + 26, f"{best['wins']} – {best['losses']}", 21, theme.AMBER_D if top else theme.INK2, True, "rm")
    if rows:
        c.text(990, 652, "Your name could be here", 14, theme.FAINT, True, "mm")
    else:
        c.text(990, 330, "No matches yet", 24, theme.INK2, True, "mm")
        c.text(990, 366, "Be the first to beat the AI!", 17, theme.MUTED, False, "mm")
    return c


# ---------------------------------------------------------------- 2. name, 3. camera check
def _build_name(c):
    draw_card(c, 290, 236, 700, 112, glow=theme.PLAYER)


def _name(session, L, now):
    c = _begin(L, "name", _build_name)
    c.rect(290, 236, 700, 112, fill=theme.PLAYER, radius=22)
    c.rect(293, 239, 694, 106, fill=theme.CARD, radius=19)
    c.spaced(640, 64, "STEP 1 OF 2", 13, theme.FAINT)
    c.text(640, 128, "What's your name?", 46, theme.INK, True, "mm")
    c.text(640, 180, "It goes on the leaderboard if you beat the AI.", 19, theme.MUTED, False, "mm")
    cursor = "|" if int(now * 2) % 2 == 0 else " "
    if session.input_text:
        c.runs(640, 292, [(session.input_text, theme.INK), (cursor, theme.PLAYER)], 56)
    else:
        c.text(640, 292, "Your name", 56, theme.TRACK, True, "mm")
        if cursor == "|":
            c.rect(638, 262, 3, 60, fill=theme.PLAYER)
    c.text(640, 390, f"Up to {config.NAME_MAX_LENGTH} letters. Leave it empty to play as Guest.", 15, theme.FAINT, False, "mm")
    c.rect(440, 436, 400, 58, fill=theme.PLAYER, radius=14)
    width = max(26, c.tw("ENTER", 13, True) + 16) + 10 + c.tw("Continue", 17, True)
    x = 640 - width / 2
    edge = _keycap(c, x, 465, "ENTER")
    c.text(edge + 10, 465, "Continue", 17, theme.WHITE, True)
    _hints(c, [("ESC", "Back")], 650 + 22)
    return c


def _build_check(c):
    draw_card(c, 730, 156, 490, 440, accent=theme.PLAYER)


def _check_screen(session, L, now, live_gesture, view):
    c = _begin(L, "check", _build_check)
    c.spaced(640, 40, "STEP 2 OF 2", 13, theme.FAINT)
    c.text(640, 84, "Check your camera", 36, theme.INK, True, "mm")
    c.text(640, 124, "Hold your hand up until everything is ticked.", 17, theme.MUTED, False, "mm")
    _camera(c, view, CHECK_CAM, "Waiting for the camera")
    x, y, w, h = CHECK_CAM
    progress = session.hold_progress(now)
    _hold_ring(c, x, y, w, h, progress)
    hand = view is not None and view.hand_found
    if session.check_passed:
        _pill(c, x + w / 2, y + h - 38, "All set!", theme.GREEN_D)
    elif progress > 0:
        left = max(0.0, config.HOLD_TO_START_SECONDS * (1 - progress))
        _pill(c, x + w / 2, y + h - 38, f"Hold still… {left:.1f} s", theme.PLAYER)
    else:
        _pill(c, x + w / 2, y + h - 38, "Hold your hand up" if not hand else "Hold your hand still", theme.AMBER_D)
    steps = [("Camera connected", True), ("Hand detected", hand or progress > 0), ("Hold still for 2 seconds", session.check_passed)]
    for i, (label, ok) in enumerate(steps):
        cy = 206 + i * 56
        if ok:
            _check(c, 778, cy)
        else:
            _spinner(c, 778, cy, now)
        c.text(814, cy, label, 19, theme.INK if ok else theme.AMBER_D, True)
    c.rect(760, 364, 430, 1, fill=theme.CARD_LINE)
    if session.check_passed:
        c.rect(760, 384, 430, 62, fill=theme.PLAYER, radius=16)
        width = max(26, c.tw("SPACE", 13, True) + 16) + 10 + c.tw("Start the match", 20, True)
        edge = _keycap(c, 975 - width / 2, 415, "SPACE")
        c.text(edge + 10, 415, "Start the match", 20, theme.WHITE, True)
        top, size = 462, 70
    else:
        c.spaced(760, 392, "HOW A ROUND WORKS", 12, theme.FAINT, spacing=3, anchor="l")
        top, size = 412, 96
    for i, move in enumerate(CHOICES):
        _tile(c, 760 + i * 112, top, 96, size, move, "p", True)
    c.wrapped(760, 541, "Throw on SHOOT! Rock beats scissors, scissors beat paper, paper beats rock.", 14, theme.MUTED, 430, 19)
    _hints(c, [("SPACE", "Start the match" if session.check_passed else "Skip the wait"), ("ESC", "Back")], 678)
    return c


# ---------------------------------------------------------------- 4. the match
def _build_match(c):
    draw_card(c, 28, CARD_TOP, 440, CARD_H, accent=theme.PLAYER)
    draw_card(c, 812, CARD_TOP, 440, CARD_H, accent=theme.AI)
    draw_card(c, 500, CARD_TOP, 280, CARD_H)
    x, y, w, h = AI_PANEL
    panel = _gradient(c.L, c.L.d(w), c.L.d(h), theme.CLOUD_TOP, theme.CLOUD_BOTTOM)
    c.paste_rounded(panel, x, y, w, h, 16)


def _learn_panel(c, session):
    """What the AI expected, drawn over the bottom of its panel. Only after the reveal, and only in Learn mode."""
    x, y, w, h = LEARN_BOX
    prediction = session.prediction
    c.rect(x, y, w, h, fill=theme.AI_L, radius=14)
    c.rect(x + 1, y + 1, w - 2, h - 2, fill=theme.AI_T, radius=13)
    evidence_colors = {"LOW": theme.AMBER_D, "MEDIUM": theme.PLAYER_D, "HIGH": theme.GREEN_D}
    c.text(x + 206, y + 20, f"EVIDENCE: {prediction.evidence}", 12, evidence_colors[prediction.evidence], True)
    for size, line_height, max_lines in ((13.5, 17, 5), (12.5, 16, 6), (11.5, 15, 6)):
        if len(c.wrap_lines(session.explanation, size, 194)) <= max_lines:
            break
    c.wrapped(x + 206, y + 44, session.explanation, size, theme.INK2, 194, line_height, max_lines=max_lines)
    base, max_h = y + 110, 68
    chance_y = base - max_h / 3
    c.dashed_line(x + 8, chance_y, x + 166, chance_y, theme.FAINT, 1.5, 5, 4)
    c.text(x + 200, chance_y, "chance", 10, theme.FAINT, False, "rm")
    top = prediction.expected
    for i, move in enumerate(CHOICES):
        bx = x + 12 + i * 56
        probability = prediction.probs[move]
        bar_h = max(6, round(max_h * probability))
        thrown = move == session.player_move
        if thrown:
            c.rect(bx - 3, base - bar_h - 3, 50, bar_h + 6, fill=theme.PLAYER, radius=10)
        c.rect(bx, base - bar_h, 44, bar_h, fill=theme.AI if move == top else theme.AI_L, radius=8)
        c.rect(bx + 4, base - bar_h - 21, 36, 18, fill=theme.AI_T)
        c.text(bx + 22, base - bar_h - 12, f"{round(probability * 100)}%", 13, theme.INK2, True, "mm")
        c.text(bx + 22, base + 14, move.capitalize(), 11, theme.PLAYER if thrown else theme.MUTED, True, "mm")


def _pips(c, flags, total, current):
    first = math.ceil(total / 2)
    for row, (start, end) in enumerate(((0, first), (first, total))):
        n = end - start
        gap = 8 if first <= 8 else 5
        size = min(24, (256 - gap * (first - 1)) // first)
        x0 = 640 - (n * size + (n - 1) * gap) / 2
        for k in range(n):
            i = start + k
            x, y = x0 + k * (size + gap), CARD_TOP + 418 + row * 30
            if i < len(flags):
                c.circle(x + size / 2, y + size / 2, size / 2, fill=theme.RESULT_COLORS[flags[i]])
                c.text(x + size / 2, y + size / 2 - 1, flags[i], 11, theme.WHITE, True, "mm")
            else:
                if i == current:
                    c.circle(x + size / 2, y + size / 2, size / 2 + 3, fill=theme.PLAYER_T)
                c.circle(x + size / 2, y + size / 2, size / 2, fill=theme.CARD,
                         outline=theme.PLAYER if i == current else (195, 203, 216), width=2)


def _match(session, L, now, live_gesture, view):
    state = session.state
    revealed = state == STATE_SHOW_RESULT
    valid = revealed and session.round_result != "INVALID"
    win = {"PLAYER": "p", "AI": "a"}.get(session.round_result) if revealed else None
    c = _begin(L, "match", _build_match)
    head = CARD_TOP + 32    # the line with the name and the status chip

    # ---- your card
    c.text(52, head, (session.player_name or "").upper(), 26, theme.PLAYER, True)
    hand = view is not None and view.hand_found
    if revealed:
        if valid:
            _chip(c, 452, head, f"Final: {session.player_move}", theme.PLAYER_D, theme.PLAYER_T)
        else:
            _chip(c, 452, head, "No hand seen", theme.AMBER_D, theme.AMBER_T)
    elif live_gesture:
        _chip(c, 452, head, f"{live_gesture.capitalize()} detected", theme.PLAYER_D, theme.PLAYER_T)
    elif hand:
        _chip(c, 452, head, "Hand detected", theme.PLAYER_D, theme.PLAYER_T)
    else:
        _chip(c, 452, head, "Looking for your hand", theme.AMBER_D, theme.AMBER_T)

    cx, cy, cw, ch = MATCH_CAM
    _camera(c, view, MATCH_CAM)
    if state == STATE_COUNTDOWN:
        _pill(c, cx + cw / 2, cy + 32, "Show your gesture on SHOOT!", theme.INK, 14)
    elif revealed and not valid:
        _pill(c, cx + cw / 2, cy + 32, "Hold your hand up before SHOOT", theme.AMBER_D, 14)
    elif not hand:
        _pill(c, cx + cw / 2, cy + 32, "Show your hand", theme.AMBER_D, 14)

    # ---- the AI's card
    c.text(836, head, "ADAPTIVE AI", 22, theme.AI, True)
    if session.learn_mode:
        _chip(c, 1236, head, "Learn mode", theme.PLAYER_D, theme.PLAYER_T, dot=True)
    else:
        _chip(c, 1236, head, "Challenge", theme.MUTED, theme.CHIP, dot=True)
    px, py, pw, ph = AI_PANEL
    mid = py + ph / 2
    if valid:
        learn = session.learn_mode
        room = (LEARN_BOX[1] - py - 8) if learn else ph - 8     # in Learn mode the hand sits above the learn box
        scale = ROCK_SCALE if session.ai_move == "ROCK" else 1
        icon = gesture_icon(session.ai_move, L.d(room * scale), upside_down=True)
        if icon is not None:
            c.paste_centered(icon, px + pw / 2, py + 4)
        else:
            c.text(px + pw / 2, mid, session.ai_move, 40, theme.AI, True, "mm")
        if learn:
            _learn_panel(c, session)
    elif state == STATE_COUNTDOWN:
        dots = "." * (int(now * 3) % 4)
        c.text(px + pw / 2 - c.tw("DECIDING...", 34, True) / 2, mid - 30, "DECIDING" + dots, 34, theme.INK, True)
        c.text(px + pw / 2, mid + 14, "Its move is locked in", 17, theme.MUTED, False, "mm")
    elif revealed:
        c.text(px + pw / 2, mid - 30, "NO ROUND", 34, theme.INK, True, "mm")
        c.text(px + pw / 2, mid + 14, "Nothing was counted", 17, theme.MUTED, False, "mm")
    else:
        c.text(px + pw / 2, mid - 30, "READY", 34, theme.INK, True, "mm")
        c.text(px + pw / 2, mid + 14, "The AI is waiting", 17, theme.MUTED, False, "mm")

    if win:
        x0 = 300 if win == "p" else 1084
        c.rect(x0, CARD_TOP - 14, 160, 28, fill=theme.GREEN, radius=14)
        c.spaced(x0 + 80, CARD_TOP, "WINNER", 13, theme.WHITE, spacing=2)

    _middle(c, session, now, valid)
    return c


def _middle(c, session, now, valid):
    state = session.state
    total = session.match_rounds or 15
    t = CARD_TOP
    c.spaced(640, t + 30, "ROUND", 12, theme.FAINT, spacing=3)
    number = str(session.round_number)
    parts = [(number, theme.INK, 44), (f" / {session.match_rounds}" if session.match_rounds else "", theme.FAINT, 22)]
    width = sum(c.tw(text, s, True) for text, _, s in parts)
    x = 640 - width / 2
    for text, colour, size in parts:
        c.text(x, t + (66 if size == 44 else 68), text, size, colour, True)
        x += c.tw(text, size, True)
    for x0, label, value, colour, tint in ((514, "YOU", session.score_player, theme.PLAYER, theme.PLAYER_T),
                                           (648, "AI", session.score_ai, theme.AI, theme.AI_T)):
        c.rect(x0, t + 90, 118, 76, fill=colour, radius=16)
        c.rect(x0 + 2, t + 92, 114, 72, fill=tint, radius=14)
        c.text(x0 + 59, t + 108, label, 13, colour, True, "mm")
        c.text(x0 + 59, t + 141, str(value), 38, theme.INK, True, "mm")

    if state == STATE_COUNTDOWN:
        elapsed = now - session.state_start_time
        remaining = session.countdown_duration - elapsed
        progress = max(0.0, min(1.0, elapsed / session.countdown_duration))
        cy = t + 262
        c.circle(640, cy, 76, fill=theme.TRACK)
        if progress > 0:
            c.pie(640, cy, 76, -90, -90 + 360 * progress, theme.PLAYER)
        c.circle(640, cy, 67, fill=theme.CARD)
        number = "3" if remaining > 2 else "2" if remaining > 1 else "1" if remaining > 0 else "GO"
        c.glyph_text(640, cy, number, 90 if number != "GO" else 60, theme.PLAYER, True)
        beat = 0 if remaining > 2 else 1 if remaining > 1 else 2 if remaining > 0 else 3
        words = ["ROCK", "PAPER", "SCISSORS", "SHOOT!"]
        chant = []
        for i, word in enumerate(words):
            chant.append((word, theme.PLAYER if i == beat else theme.FAINT))
            if i < 3:
                chant.append((" · ", theme.FAINT))
        c.runs(640, t + 372, chant, 12.5)
    elif state == STATE_SHOW_RESULT and valid:
        kind = session.round_result
        title, colour = {"PLAYER": ("YOU WIN!", theme.GREEN_D), "AI": ("AI WINS", theme.RED_D),
                         "TIE": ("DRAW", theme.AMBER_D)}[kind]
        c.text(640, t + 204, title, 34, colour, True, "mm")
        _tile(c, 522, t + 228, 104, 120, session.player_move, "p", True)
        _tile(c, 654, t + 228, 104, 120, session.ai_move, "ai", True, hanging=True)
        c.text(640, t + 288, "vs", 13, theme.FAINT, True, "mm")
        if kind == "PLAYER":
            why, delta = f"{session.player_move} beats {session.ai_move}", "+1 point for you"
        elif kind == "AI":
            why, delta = f"{session.ai_move} beats {session.player_move}", "+1 point for the AI"
        else:
            why, delta = f"You both threw {session.player_move}", "No points this round"
        c.text(640, t + 372, why, 15, theme.INK2, True, "mm")
        c.text(640, t + 396, delta, 14, colour, True, "mm")
    elif state == STATE_SHOW_RESULT:
        c.text(640, t + 204, "MISSED IT", 30, theme.AMBER_D, True, "mm")
        c.circle(640, t + 274, 50, fill=theme.AMBER_T)
        for k in range(18):
            c.arc(640, t + 274, 49, k * 20, k * 20 + 11, theme.AMBER, 3)
        c.glyph_text(640, t + 274, "?", 46, theme.AMBER_D, True)
        c.wrapped(520, t + 346, "No gesture was seen, so this round doesn't count. Go again!", 14, theme.MUTED, 240, 19, align="c")
    else:
        c.text(640, t + 204, "GET READY", 28, theme.INK, True, "mm")
        c.circle(640, t + 278, 52, fill=theme.PLAYER)
        c.polygon([(627, t + 256), (627, t + 300), (666, t + 278)], theme.WHITE)
        group = c.tw("Press", 15) + 6 + max(26, c.tw("SPACE", 13, True) + 16)
        c.text(640 - group / 2, t + 360, "Press", 15, theme.MUTED)
        _keycap(c, 640 - group / 2 + c.tw("Press", 15) + 6, t + 360, "SPACE")

    flags = [{"PLAYER": "W", "AI": "L", "TIE": "D"}[r.result] for r in session.match_log]
    if not session.match_rounds:
        flags = flags[-total:]
    _pips(c, flags, total, len(flags) if len(flags) < total else -1)
    if session.streak:
        c.runs(640, t + 496, [(f"STREAK {session.streak}", theme.AMBER_D), (f" · best {session.best_streak}", theme.FAINT)], 14)
    else:
        c.text(640, t + 496, "No streak yet", 14, theme.FAINT, True, "mm")

    if state == STATE_COUNTDOWN:
        hints = [("Q", "Quit")]
    elif state == STATE_SHOW_RESULT:
        after = "See your report" if session.match_complete else ("Go again" if not valid else "Next round")
        hints = [("SPACE", after), ("P", "New player"), ("H", "Hide thinking" if session.learn_mode else "Learn mode"), ("Q", "Quit")]
    else:
        hints = [("SPACE", "Start round"), ("P", "New player"), ("H", "Learn mode"), ("Q", "Quit")]
    _hints(c, hints)


# ---------------------------------------------------------------- 5. report, every round
def _gauge(c, cx, cy, r, fraction):
    for t0, t1, colour in ((0, .4, (74, 222, 128)), (.4, .6, (251, 191, 36)), (.6, 1, (248, 113, 113))):
        c.arc(cx, cy, r, 180 + 180 * t0, 180 + 180 * t1, colour, 24)
    point = lambda t, rr: (cx + rr * math.cos(math.pi * (1 - t)), cy - rr * math.sin(math.pi * (1 - t)))
    c.line([point(1 / 3, r - 18), point(1 / 3, r + 18)], theme.INK, 3)
    c.text(point(1 / 3, r + 34)[0] - 6, point(1 / 3, r + 34)[1], "chance", 12, theme.MUTED, True, "rm")
    c.line([(cx, cy), point(fraction, r - 34)], theme.INK, 6)
    c.circle(cx, cy, 11, fill=theme.INK)


def _build_summary(c):
    draw_card(c, 40, 128, 380, 430, accent=theme.AI)
    draw_card(c, 440, 128, 400, 430, accent=theme.PLAYER)
    draw_card(c, 860, 128, 380, 430)


def _summary(session, L, now):
    summary = session.summary
    c = _begin(L, "summary", _build_summary)
    c.spaced(60, 52, "MATCH COMPLETE", 13, theme.FAINT, spacing=3, anchor="l")
    c.text(60, 84, (session.player_name or "").upper(), 30, theme.PLAYER, True)
    headline_colour = {"YOU WIN": theme.GREEN_D, "AI WINS": theme.RED_D, "DRAW": theme.AMBER_D}[summary.headline]
    c.text(640, 58, summary.headline, 44, headline_colour, True, "mm")
    draws = f" · {summary.ties} draw{'s' if summary.ties != 1 else ''}" if summary.ties else ""
    c.text(640, 100, f"{summary.wins} – {summary.losses}{draws}", 17, theme.MUTED, False, "mm")
    if session.rank:
        c.runs(1220 - c.tw(f"#{session.rank} on the leaderboard", 17) / 2, 64,
               [(f"#{session.rank}", theme.AMBER_D), (" on the leaderboard", theme.INK2)], 17)
    else:
        c.text(1220, 64, "Play with a name to join the leaderboard" if session.is_guest else "Playing as " + session.player_name,
               15, theme.MUTED, True, "rm")

    # Your title
    index = title_index(summary)
    c.spaced(230, 168, "YOUR TITLE", 12, theme.FAINT, spacing=3)
    if index is None:
        c.text(230, 212, "TOO FEW ROUNDS", 27, theme.MUTED, True, "mm")
        c.text(230, 246, "The AI needs more throws to read you.", 15, theme.MUTED, False, "mm")
    else:
        c.text(230, 212, TITLES[index][0], 27, theme.AI, True, "mm")
        c.text(230, 246, f"The AI read {round(summary.accuracy * 100)}% of your throws.", 16, theme.MUTED, False, "mm")
    for i, (title, span, _) in enumerate(TITLES):
        y, on = 280 + i * 40, i == index
        if on:
            c.rect(66, y, 328, 34, fill=theme.AI, radius=10)
            c.rect(68, y + 2, 324, 30, fill=theme.AI_T, radius=8)
        else:
            c.rect(66, y, 328, 34, fill=theme.ROW, radius=10)
        c.text(80, y + 17, title, 14, theme.AI_D if on else theme.MUTED, True)
        c.text(380, y + 17, span, 13, theme.AI_D if on else theme.FAINT, False, "rm")
    c.spaced(230, 478, "AI PREDICTED", 12, theme.FAINT, spacing=3)
    c.runs(230, 516, [(str(summary.hits), theme.INK), (f" of {summary.predicted_rounds} throws", theme.FAINT)], 30)

    # How readable
    c.spaced(640, 168, "HOW READABLE YOU WERE", 12, theme.FAINT, spacing=3)
    _gauge(c, 640, 366, 130, summary.accuracy)
    c.text(640, 398, f"{round(summary.accuracy * 100)}%", 36, theme.INK, True, "mm")
    c.spaced(640, 438, "YOUR THROWS", 12, theme.FAINT, spacing=3)
    counts = {move: sum(r.player_move == move for r in session.match_log) for move in CHOICES}
    most = max(1, len(session.match_log))
    for i, move in enumerate(CHOICES):
        y = 464 + i * 31
        _tile(c, 466, y - 14, 28, 28, move, "p", True)
        c.text(504, y, move, 14, theme.INK2, True)
        c.rect(590, y - 8, 170, 16, fill=(222, 228, 238), radius=8)
        if counts[move]:
            c.rect(590, y - 8, max(10, round(170 * counts[move] / most)), 16, fill=theme.PLAYER, radius=8)
        c.text(814, y, str(counts[move]), 14, theme.INK2, True, "rm")

    # Habits and chart
    c.spaced(1050, 168, "HABITS IT FOUND", 12, theme.FAINT, spacing=3)
    line = 190
    for habit in summary.habits[:3]:
        line += 30 * c.wrapped(884, line, habit, 16, theme.PLAYER_D, 332, 24, max_lines=3) + 6
    c.spaced(1050, 340, "HOW THE AI DID, ROUND BY ROUND", 12, theme.FAINT, spacing=2)
    _chart(c, 892, 372, 316, 110, summary)
    c.text(1050, 510, "dashed line = chance (33%)", 12, theme.FAINT, False, "mm")

    for x, w, label, key, primary in ((284, 220, "Play again", "SPACE", True), (520, 230, "Every round", "R", False),
                                      (766, 230, "Next player", "N", False)):
        if primary:
            c.rect(x, 580, w, 56, fill=theme.PLAYER, radius=14)
        else:
            c.rect(x, 580, w, 56, fill=theme.KEY_LINE, radius=14)
            c.rect(x + 2, 582, w - 4, 52, fill=theme.CARD, radius=12)
        width = max(26, c.tw(key, 13, True) + 16) + 10 + c.tw(label, 17, True)
        edge = _keycap(c, x + w / 2 - width / 2, 608, key)
        c.text(edge + 10, 608, label, 17, theme.WHITE if primary else theme.INK2, True)
    return c


def _chart(c, x, y, w, h, summary):
    flags = summary.hit_flags
    c.dashed_line(x, y + h * 2 / 3, x + w, y + h * 2 / 3, theme.FAINT, 1.5, 6, 6)
    if not flags:
        return
    hits, points = 0, []
    for i, flag in enumerate(flags):
        hits += flag
        px = x + (i * w / (len(flags) - 1) if len(flags) > 1 else w / 2)
        points.append((px, y + h - h * hits / (i + 1)))
    if len(points) > 1:
        c.line(points, theme.AI, 3)
    for (px, py), flag in zip(points, flags):
        c.circle(px, py, 5.5, fill=theme.GREEN if flag else theme.RED, outline=theme.CARD, width=2)


def _build_replay(c):
    draw_card(c, 30, 24, 1220, 672)


def _replay(session, L, now):
    c = _begin(L, "replay", _build_replay)
    c.text(640, 66, "Every round", 34, theme.INK, True, "mm")
    c.text(640, 104, "What the AI expected, now that the match is over", 17, theme.MUTED, False, "mm")
    c.rect(60, 128, 1160, 1, fill=theme.CARD_LINE)
    log = session.match_log
    per_column = max(1, math.ceil(len(log) / 2))
    pitch = min(60, 520 / per_column)
    for i, record in enumerate(log):
        col, row = divmod(i, per_column)
        x, y = 60 + col * 580, 144 + row * pitch
        c.rect(x, y, 540, pitch - 8, fill=theme.ROW, radius=12)
        mid = y + (pitch - 8) / 2
        c.text(x + 20, mid, str(i + 1), 18, theme.MUTED, True)
        size = min(44, pitch - 16)
        _tile(c, x + 54, mid - size / 2, size, size, record.player_move, "p", True)
        c.text(x + 114, mid, "vs", 13, theme.FAINT)
        _tile(c, x + 134, mid - size / 2, size, size, record.ai_move, "ai", True, hanging=True)
        flag = {"PLAYER": "W", "AI": "L", "TIE": "D"}[record.result]
        c.circle(x + 212, mid, 12, fill=theme.RESULT_COLORS[flag])
        c.text(x + 212, mid - 1, flag, 11, theme.WHITE, True, "mm")
        c.text(x + 246, mid, f"AI expected {record.expected}" if record.expected else "AI was guessing", 15, theme.INK2)
        if record.expected:
            hit = record.expected == record.player_move
            mx, colour = x + 506, theme.GREEN if hit else theme.RED
            if hit:
                c.line([(mx - 8, mid), (mx - 2, mid + 7), (mx + 9, mid - 8)], colour, 3.4)
            else:
                c.line([(mx - 7, mid - 7), (mx + 7, mid + 7)], colour, 3.4)
                c.line([(mx - 7, mid + 7), (mx + 7, mid - 7)], colour, 3.4)
    _hints(c, [("SPACE", "Back to your report")], 672)
    return c


# ---------------------------------------------------------------- 6. overlays
def _idle_overlay(c, remaining):
    _dim(c)
    draw_card(c, 430, 190, 420, 300, accent=theme.PLAYER)
    c.text(640, 250, "Still there?", 36, theme.INK, True, "mm")
    c.text(640, 292, "This match will end soon.", 17, theme.MUTED, False, "mm")
    c.circle(640, 370, 50, fill=theme.TRACK)
    c.pie(640, 370, 50, -90, -90 + 360 * (remaining / config.IDLE_WARNING_SECONDS), theme.PLAYER)
    c.circle(640, 370, 42, fill=theme.CARD)
    c.text(640, 372, str(math.ceil(remaining)), 38, theme.PLAYER, True, "mm")
    edge = 640 - (c.tw("Show your hand or press", 15) + 8 + max(26, c.tw("any key", 13, True) + 16)) / 2
    c.text(edge, 452, "Show your hand or press", 15, theme.MUTED)
    _keycap(c, edge + c.tw("Show your hand or press", 15) + 8, 452, "any key")


def _admin_overlay(c, session):
    _dim(c)
    draw_card(c, 740, 40, 500, 640, accent=theme.AMBER)
    c.text(780, 86, "Admin", 28, theme.AMBER_D, True)
    c.text(1210, 86, "Ctrl+A or ESC to close", 13, theme.MUTED, False, "rm")
    c.rect(770, 112, 440, 1, fill=theme.CARD_LINE)
    s = session.settings
    rounds = "No limit" if s.match_rounds == 0 else str(s.match_rounds)
    rows = [
        ("Match length", "Rounds before the report", [str(n) if n else "No limit" for n in config.MATCH_ROUND_CHOICES], rounds),
        ("Default mode", "What new matches start in", ["Challenge", "Learn"], "Learn" if s.learn_mode else "Challenge"),
        ("Camera picture", "Skeleton only hides faces completely", ["Full", "Skeleton only"], "Skeleton only" if s.skeleton_only else "Full"),
        ("Return to start screen", "After this long without a hand", [f"{n} s" for n in config.IDLE_SECOND_CHOICES], f"{s.idle_seconds} s"),
        ("Leaderboard", "Press 5 twice to clear it", ["Keep", "Clear now"], "Clear now" if session.admin_clear_armed else "Keep"),
    ]
    for i, (label, hint, options, current) in enumerate(rows):
        y = 144 + i * 92
        _keycap(c, 780, y + 10, str(i + 1))
        c.text(820, y + 10, label, 18, theme.INK, True)
        c.text(780, y + 34, hint, 13, theme.MUTED)
        for k, option in enumerate(options):
            x, on = 780 + k * 102, option == current
            c.rect(x, y + 52, 96, 34, fill=theme.PLAYER if on else theme.KEY_LINE, radius=9)
            if not on:
                c.rect(x + 1, y + 53, 94, 32, fill=theme.WHITE, radius=8)
            c.text(x + 48, y + 69, option, 14, theme.WHITE if on else theme.INK2, True, "mm")
    c.text(780, 636, "Press 1 to 5 to change a setting. Saved straight away.", 14, theme.MUTED)


def render_camera_problem(w, h, now, retry_in):
    """Shown when the camera stops sending pictures. The game keeps trying by itself."""
    L = _layout(w, h)
    c = _begin(L, "camera-problem", lambda cv: draw_card(cv, 340, 150, 600, 420, accent=theme.AMBER))
    c.circle(640, 228, 44, fill=theme.AMBER_T, outline=theme.AMBER, width=4)
    c.text(640, 230, "!", 48, theme.AMBER_D, True, "mm")
    c.text(640, 318, "Camera problem", 34, theme.INK, True, "mm")
    c.text(640, 356, "The game lost the picture from the camera.", 18, theme.MUTED, False, "mm")
    for i, line in enumerate(("Check the cable or the USB port", "Close other apps using the camera (Zoom, Teams)",
                              "The game keeps trying by itself")):
        c.text(400, 408 + i * 34, f"{i + 1}   {line}", 18, theme.INK2)
    _spinner(c, 574, 525, now)
    c.text(600, 525, f"Retrying… {max(0, math.ceil(retry_in))}", 16, theme.AMBER_D, True)
    _hints(c, [("Q", "Quit")], 678)
    return _bgr(c)


# ---------------------------------------------------------------- entry point
def render_ui(session, w, h, now, live_gesture, view):
    """The whole screen for the session's current state, as a BGR picture of size h x w."""
    L = _layout(w, h)
    state = session.state
    if state == STATE_START:
        c = _start(session, L, now)
    elif state == STATE_NAME_INPUT:
        c = _name(session, L, now)
    elif state == STATE_CAMERA_CHECK:
        c = _check_screen(session, L, now, live_gesture, view)
    elif state == STATE_SUMMARY:
        c = _summary(session, L, now)
    elif state == STATE_REPLAY:
        c = _replay(session, L, now)
    else:
        c = _match(session, L, now, live_gesture, view)

    remaining = session.idle_remaining(now)
    if remaining is not None:
        _idle_overlay(c, remaining)
    if session.admin_open:
        _admin_overlay(c, session)
    return _bgr(c)
