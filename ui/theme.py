"""Fonts for the interface."""
from PIL import ImageFont


def get_font(size, bold=False):
    font_names = [
        "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\trebucbd.ttf" if bold else "C:\\Windows\\Fonts\\trebuc.ttf",
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
