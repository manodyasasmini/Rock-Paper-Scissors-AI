"""Hand symbols for the three moves, cut from the banner artwork by tools/make_gesture_icons.py."""
import os

from PIL import Image

ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "gestures")

_sources = {}
_sized = {}


def _source(move):
    if move not in _sources:
        try:
            _sources[move] = Image.open(os.path.join(ICON_DIR, f"{move.lower()}.png")).convert("RGBA")
        except OSError:
            _sources[move] = None  # caller falls back to the move's name
    return _sources[move]


def gesture_icon(move, height, opacity=1.0, upside_down=False):
    """An RGBA picture of the move, `height` pixels tall, or None if the artwork is missing.

    Upright shows the hand rising from the bottom; upside down hangs it from the top.
    """
    key = (move, height, round(opacity, 2), upside_down)
    if key not in _sized:
        source = _source(move)
        if source is None:
            _sized[key] = None
        else:
            icon = source.resize((round(source.width * height / source.height), height), Image.LANCZOS)
            if upside_down:
                icon = icon.rotate(180)
            if opacity < 1.0:
                icon.putalpha(icon.getchannel("A").point(lambda value: int(value * opacity)))
            _sized[key] = icon
    return _sized[key]
