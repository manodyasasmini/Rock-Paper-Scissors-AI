"""Play each candidate win sound in turn, so you can pick one:  python tools/preview_win_sounds.py"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import sound  # noqa: E402

player = sound.Sounds()
for label, notes in sound.WIN_OPTIONS.items():
    sound.SOUNDS["win"] = notes
    player._files.pop("win", None)
    print(label, flush=True)
    player.play("win")
    time.sleep(2.0)
