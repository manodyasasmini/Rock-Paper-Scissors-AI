"""Colours and fonts. Every screen takes its look from here."""
from functools import lru_cache

from PIL import ImageFont

# The screens are designed on a 1280 x 720 canvas and scaled to whatever size the camera frame is.
DESIGN_W = 1280
DESIGN_H = 720

# Teal is the player, red is the AI, green/red/amber are results.
BG = (227, 231, 238)
CARD = (246, 248, 251)
CARD_LINE = (211, 217, 227)
ROW = (235, 239, 245)
TRACK = (211, 217, 227)
INK = (31, 41, 55)
INK2 = (55, 65, 81)
MUTED = (91, 101, 117)
FAINT = (138, 147, 163)
WHITE = (255, 255, 255)

PLAYER = (13, 148, 136)
PLAYER_D = (15, 118, 110)
PLAYER_T = (215, 240, 238)
AI = (220, 38, 38)
AI_D = (176, 25, 25)
AI_T = (253, 234, 234)
AI_L = (243, 166, 166)

GREEN = (22, 163, 74)
GREEN_D = (15, 122, 55)
GREEN_T = (227, 246, 233)
AMBER = (245, 158, 11)
AMBER_D = (154, 91, 0)
AMBER_T = (255, 243, 214)

TILE = (31, 41, 55)
TILE_LINE = (55, 65, 81)
TILE_PLAYER = (19, 78, 74)
TILE_AI = (76, 29, 29)
CLOUD_TOP = (241, 245, 249)
CLOUD_BOTTOM = (203, 213, 225)
CHIP = (230, 234, 241)
KEY_LINE = (205, 213, 230)

MEDALS = [(245, 179, 1), (170, 180, 195), (205, 127, 50)]
RESULT_COLORS = {"W": GREEN, "L": AI, "D": AMBER}

_FONT_FILES = {
    False: ["C:\\Windows\\Fonts\\segoeui.ttf", "C:\\Windows\\Fonts\\arial.ttf", "C:\\Windows\\Fonts\\trebuc.ttf"],
    True: ["C:\\Windows\\Fonts\\segoeuib.ttf", "C:\\Windows\\Fonts\\arialbd.ttf", "C:\\Windows\\Fonts\\trebucbd.ttf"],
}


@lru_cache(maxsize=None)
def get_font(pixels, bold=False):
    for path in _FONT_FILES[bool(bold)]:
        try:
            return ImageFont.truetype(path, pixels)
        except OSError:
            continue
    return ImageFont.load_default()
