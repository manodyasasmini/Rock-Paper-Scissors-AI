"""Render pictures of every screen, for the README and the poster. No camera or saved data is touched.

    python tools/make_screenshots.py

The camera picture is replaced by the plain grid ("skeleton only" mode) with a pretend hand, so no face appears.
The leaderboard names are made up. For the poster you may prefer real screenshots from a real game.
"""
import os
import random
import sys
import tempfile

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ai.engine import AdaptiveEngine  # noqa: E402
from game.session import GameSession, KEY_CTRL_A, KEY_ENTER, KEY_SPACE  # noqa: E402
from game.settings import Settings  # noqa: E402
from game.store import PlayerStore  # noqa: E402
from ui.camera import render_camera  # noqa: E402
from ui.screens import camera_size, render_ui  # noqa: E402

SAMPLE_PLAYERS = {"Alex": (11, 3), "Sami": (10, 4), "Jo": (10, 5), "Nima": (9, 4), "Kavi": (9, 5),
                  "Luna": (8, 5), "Ravi": (8, 6), "Mira": (7, 6)}
PATTERN = ["ROCK", "ROCK", "PAPER"]


def make_hand(gesture, cx=0.5, cy=0.5, palm=0.2):
    """21 normalised landmarks of an upright pretend hand."""
    pts = {0: (cx, cy + palm / 2), 1: (cx - 0.4 * palm, cy + 0.3 * palm), 2: (cx - 0.7 * palm, cy),
           3: (cx - 0.9 * palm, cy - 0.25 * palm), 4: (cx - palm, cy - 0.45 * palm)}
    extended = {"ROCK": [], "PAPER": [0, 1, 2, 3], "SCISSORS": [0, 1]}[gesture]
    for finger, x in enumerate((cx - 0.45 * palm, cx, cx + 0.4 * palm, cx + 0.75 * palm)):
        base, top = 5 + 4 * finger, cy - palm / 2
        pts[base] = (x, top)
        for k, reach in enumerate((0.45, 0.70, 0.95) if finger in extended else (0.35, 0.05, -0.10)):
            pts[base + 1 + k] = (x, top - reach * palm)
    return [(cx + (pts[i][0] - cx) * 9 / 16, pts[i][1]) for i in range(21)]   # square on a 16:9 frame


def main():
    out_demo = os.path.join(ROOT, "demo")
    out_poster = os.path.join(ROOT, "design", "poster-assets")
    os.makedirs(out_demo, exist_ok=True)
    os.makedirs(out_poster, exist_ok=True)

    store = PlayerStore(os.path.join(tempfile.mkdtemp(), "players.json"))     # a throwaway file
    for name, (wins, losses) in SAMPLE_PLAYERS.items():
        store.save_player(name, {"best_match": {"wins": wins, "losses": losses, "ties": 15 - wins - losses, "fav": "ROCK"}})
    settings = Settings()
    settings.skeleton_only = True
    s = GameSession(store, AdaptiveEngine(rng=random.Random(5)), settings)

    frame = np.zeros((720, 1280, 3), np.uint8)
    saved = {}

    def view(gesture="PAPER", size=(1920, 1080)):
        return render_camera(frame, make_hand(gesture), *camera_size(s.state, *size), skeleton_only=True)

    def shot(name, now, live=None, hand=None, poster=None):
        v = view(hand or live or "PAPER") if s.tracking_active else None
        saved[name] = render_ui(s, 1920, 1080, now, live, v)
        if poster:
            small = view(hand or live or "PAPER", (1280, 720)) if s.tracking_active else None
            cv2.imwrite(os.path.join(out_poster, poster), render_ui(s, 1280, 720, now, live, small))

    now = 100.0
    shot("01-start", now)
    s.handle_key(KEY_SPACE, now)
    for ch in "Nadee":
        s.handle_key(ord(ch), now)
    shot("02-name", now)
    s.input_text = "Alex"
    s.handle_key(KEY_ENTER, now)
    shot("03-is-this-you", now)
    s.handle_key(ord("n"), now)
    s.input_text = "Nadee"
    s.handle_key(KEY_ENTER, now)
    s.update(now + 1, "PAPER")
    s.update(now + 2.2, "PAPER")
    shot("04-camera-check", now + 2.2, "PAPER")
    s.update(now + 3.5, "PAPER")
    s.start_new_match(now + 4)
    shot("05-ready", now + 4, None, "PAPER", poster="arena-ready.png")

    now += 5
    player = random.Random(11)          # a player with no pattern, so the AI cannot read them
    shown = set()
    for i in range(13):
        s.start_round(now)
        if i == 6:
            shot("06-countdown", now + 1.5, "ROCK", hand="ROCK")
        move = player.choice(["ROCK", "PAPER", "SCISSORS"])
        s.update(now + 3.1, move)
        now += 10
        name = {"PLAYER": "07-you-win", "AI": "08-ai-wins", "TIE": "09-draw"}[s.round_result]
        if name not in shown and i >= 3:
            shown.add(name)
            shot(name, now, s.player_move, poster="result.png" if name == "07-you-win" else None)
        if "10-learn-mode" not in shown and i >= 4 and s.prediction.expected is not None and s.round_result != "TIE":
            shown.add("10-learn-mode")
            s.learn_mode = True
            shot("10-learn-mode", now, s.player_move, poster="learn-mode.png")
            s.learn_mode = False
    s.start_round(now)
    s.update(now + 3.1, None)                 # no hand: a missed round, which does not count
    shot("11-missed", now + 4, None, "PAPER")
    now += 10
    while not s.match_complete:
        s.start_round(now)
        s.update(now + 3.1, player.choice(["ROCK", "PAPER", "SCISSORS"]))
        now += 10
    s.handle_key(KEY_SPACE, now)
    shot("12-report", now + 1, poster="summary.png")
    s.handle_key(ord("r"), now + 2)
    shot("13-every-round", now + 2)
    s.handle_key(KEY_SPACE, now + 3)
    s.handle_key(KEY_CTRL_A, now + 4)
    shot("14-admin", now + 4)

    for name, image in saved.items():
        cv2.imwrite(os.path.join(out_demo, name + ".png"), image)
    print(f"wrote {len(saved)} pictures to demo/ and 4 to design/poster-assets/")


if __name__ == "__main__":
    main()
