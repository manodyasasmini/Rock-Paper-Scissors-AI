"""Put screenshots inside a screen frame (just the display, no laptop base), with a transparent background.

    python tools/make_laptop_mockups.py                 # the four poster pictures, plus an empty frame
    python tools/make_laptop_mockups.py shot1.png ...   # your own screenshots
    add --laptop to include the laptop base

Each result is saved as screen-<name>.png (laptop-<name>.png with --laptop) in design/poster-assets/.
`screen-frame-empty.png` has a transparent screen: place it above a picture in Canva and the picture shows through.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "design", "poster-assets")

SCREEN_W, SCREEN_H = 1920, 1080     # the screen's picture area, in pixels
SIDE, TOP, BOTTOM = 38, 40, 46      # bezel widths around the screen
PAD = 70                            # transparent margin around the laptop, for the shadow
SS = 2                              # drawn at twice the size and shrunk, so edges are smooth

LID_W = SCREEN_W + 2 * SIDE
LID_H = SCREEN_H + TOP + BOTTOM
BASE_W = int(LID_W * 1.1)
BASE_H = 58


def _dims(with_base):
    width = (BASE_W if with_base else LID_W) + 2 * PAD
    height = LID_H + (BASE_H if with_base else 0) + 2 * PAD
    lid_x = (width - LID_W) // 2
    screen_box = (lid_x + SIDE, PAD + TOP, lid_x + SIDE + SCREEN_W, PAD + TOP + SCREEN_H)
    return width, height, lid_x, PAD, screen_box


def _gradient(size, top, bottom):
    w, h = size
    column = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        column.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return column.resize((w, h))


def make_frame(with_base=False):
    """The screen (and the laptop base, if asked) on a transparent background, with a see-through screen."""
    WIDTH, HEIGHT, LID_X, LID_Y, SCREEN_BOX = _dims(with_base)
    big = (WIDTH * SS, HEIGHT * SS)
    layer = Image.new("RGBA", big, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    s = lambda *values: [v * SS for v in values]

    # soft shadow under the base
    shadow = Image.new("L", big, 0)
    foot = LID_Y + LID_H + (BASE_H if with_base else 0)
    ImageDraw.Draw(shadow).ellipse(s(LID_X - 20, foot - 18, LID_X + LID_W + 20, foot + 40), fill=120 if with_base else 90)
    shadow = shadow.filter(ImageFilter.GaussianBlur(26 * SS))
    layer.paste(Image.new("RGBA", big, (20, 28, 50, 255)), (0, 0), shadow)

    if with_base:
        # base: a flat silver slab with a rounded front edge
        base_x = (WIDTH - BASE_W) // 2
        base_y = LID_Y + LID_H - 2
        base_mask = Image.new("L", big, 0)
        bd = ImageDraw.Draw(base_mask)
        bd.rounded_rectangle(s(base_x, base_y - 30, base_x + BASE_W, base_y + BASE_H), radius=30 * SS, fill=255)
        bd.rectangle(s(base_x, base_y - 30, base_x + BASE_W, base_y), fill=255)
        base_fill = _gradient(big, (222, 226, 233), (170, 177, 190)).convert("RGBA")
        layer.paste(base_fill, (0, 0), base_mask)
        draw.rounded_rectangle(s(WIDTH // 2 - 190, base_y, WIDTH // 2 + 190, base_y + 17), radius=9 * SS, fill=(120, 128, 143, 255))

    # lid: dark bezel with a faint edge light
    draw.rounded_rectangle(s(LID_X, LID_Y, LID_X + LID_W, LID_Y + LID_H), radius=34 * SS, fill=(54, 63, 82, 255))
    draw.rounded_rectangle(s(LID_X + 2, LID_Y + 2, LID_X + LID_W - 2, LID_Y + LID_H - 2), radius=32 * SS, fill=(24, 30, 44, 255))
    cx = WIDTH // 2
    draw.ellipse(s(cx - 7, LID_Y + 14, cx + 7, LID_Y + 28), fill=(44, 54, 74, 255))
    draw.ellipse(s(cx - 3, LID_Y + 18, cx + 3, LID_Y + 24), fill=(10, 14, 24, 255))

    # cut the screen out, so a picture placed behind the frame shows through
    hole = Image.new("L", big, 255)
    ImageDraw.Draw(hole).rounded_rectangle(s(*SCREEN_BOX), radius=10 * SS, fill=0)
    layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", big, 0), hole))
    return layer.resize((WIDTH, HEIGHT), Image.LANCZOS)


def put_in_laptop(screenshot_path=None, with_base=False):
    """The frame with this screenshot on its screen (or an empty see-through screen)."""
    WIDTH, HEIGHT, _, _, SCREEN_BOX = _dims(with_base)
    result = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    if screenshot_path:
        shot = Image.open(screenshot_path).convert("RGB")
        scale = max(SCREEN_W / shot.width, SCREEN_H / shot.height)        # fill the screen, cropping any excess
        shot = shot.resize((round(shot.width * scale), round(shot.height * scale)), Image.LANCZOS)
        left, top = (shot.width - SCREEN_W) // 2, (shot.height - SCREEN_H) // 2
        result.paste(shot.crop((left, top, left + SCREEN_W, top + SCREEN_H)), SCREEN_BOX[:2])
    result.alpha_composite(make_frame(with_base))
    return result


def main(args):
    with_base = "--laptop" in args
    paths = [a for a in args if not a.startswith("--")]
    prefix = "laptop" if with_base else "screen"
    os.makedirs(OUT, exist_ok=True)
    if not paths:
        demo = os.path.join(ROOT, "demo")
        paths = [os.path.join(demo, name) for name in ("05-ready.png", "07-you-win.png", "10-learn-mode.png", "12-report.png")]
        put_in_laptop(None, with_base).save(os.path.join(OUT, f"{prefix}-frame-empty.png"))
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        put_in_laptop(path, with_base).save(os.path.join(OUT, f"{prefix}-{name}.png"))
        print("wrote", f"{prefix}-{name}.png")


if __name__ == "__main__":
    main(sys.argv[1:])
