"""Drawing in design units (1280 x 720). The canvas scales everything to the real frame size."""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ui import theme
from ui.theme import get_font


class Layout:
    """Maps the 1280 x 720 design onto a w x h frame, centred, never stretched."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.s = min(w / theme.DESIGN_W, h / theme.DESIGN_H)
        self.ox = (w - theme.DESIGN_W * self.s) / 2
        self.oy = (h - theme.DESIGN_H * self.s) / 2

    def x(self, v):
        return round(self.ox + v * self.s)

    def y(self, v):
        return round(self.oy + v * self.s)

    def d(self, v):
        return max(1, round(v * self.s))

    def box(self, x, y, w, h):
        """Pixel (x1, y1, x2, y2) of a design rectangle."""
        return self.x(x), self.y(y), self.x(x + w), self.y(y + h)


def make_background(layout):
    """The cool grey screen with a soft teal glow top left and a red one bottom right."""
    w, h = layout.w, layout.h
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    base = np.empty((h, w, 3), dtype=np.float32)
    base[:] = theme.BG
    for (cx, cy, rx, colour, strength) in ((0.10, 0.06, 0.45, theme.PLAYER, 0.14), (0.92, 0.94, 0.48, theme.AI, 0.08)):
        distance = np.hypot((xs - cx * w) / (rx * w), (ys - cy * h) / (rx * w))
        alpha = (np.clip(1 - distance, 0, 1) * strength)[..., None]
        base = base * (1 - alpha) + np.array(colour, dtype=np.float32) * alpha
    return Image.fromarray(base.astype(np.uint8), "RGB")


class Canvas:
    def __init__(self, image, layout):
        self.img = image
        self.L = layout
        self.d = ImageDraw.Draw(image)

    # ---- shapes ----
    def rect(self, x, y, w, h, fill=None, outline=None, width=1, radius=0):
        box = self.L.box(x, y, w, h)
        box = (box[0], box[1], max(box[0] + 1, box[2] - 1), max(box[1] + 1, box[3] - 1))
        line = self.L.d(width) if outline else 0
        if radius:
            self.d.rounded_rectangle(box, radius=self.L.d(radius), fill=fill, outline=outline, width=line)
        else:
            self.d.rectangle(box, fill=fill, outline=outline, width=line)

    def circle(self, cx, cy, r, fill=None, outline=None, width=1):
        L = self.L
        self.d.ellipse([L.x(cx - r), L.y(cy - r), L.x(cx + r), L.y(cy + r)], fill=fill,
                       outline=outline, width=L.d(width) if outline else 0)

    def arc(self, cx, cy, r, start, end, fill, width):
        L = self.L
        self.d.arc([L.x(cx - r), L.y(cy - r), L.x(cx + r), L.y(cy + r)], start, end, fill=fill, width=L.d(width))

    def pie(self, cx, cy, r, start, end, fill):
        L = self.L
        self.d.pieslice([L.x(cx - r), L.y(cy - r), L.x(cx + r), L.y(cy + r)], start, end, fill=fill)

    def line(self, points, fill, width=1):
        self.d.line([(self.L.x(px), self.L.y(py)) for px, py in points], fill=fill, width=self.L.d(width), joint="curve")

    def dashed_line(self, x1, y1, x2, y2, fill, width=1, dash=7, gap=7):
        length = math.hypot(x2 - x1, y2 - y1)
        steps = int(length // (dash + gap)) + 1
        for i in range(steps):
            a = i * (dash + gap) / length
            b = min(1.0, (i * (dash + gap) + dash) / length)
            self.line([(x1 + (x2 - x1) * a, y1 + (y2 - y1) * a), (x1 + (x2 - x1) * b, y1 + (y2 - y1) * b)], fill, width)

    # ---- text ----
    def font(self, size, bold=False):
        return get_font(max(8, round(size * self.L.s)), bold)

    def tw(self, text, size, bold=False):
        """Width of `text` in design units."""
        key = (text, size, bold, self.L.s)
        if key not in _widths:
            _widths[key] = self.font(size, bold).getlength(text) / self.L.s
        return _widths[key]

    def text(self, x, y, text, size, fill, bold=False, anchor="lm"):
        self.d.text((self.L.x(x), self.L.y(y)), text, font=self.font(size, bold), fill=fill, anchor=anchor)

    def spaced(self, x, y, text, size, fill, bold=True, spacing=3, anchor="mm"):
        """Text with extra space between the letters, for small caps labels."""
        font = self.font(size, bold)
        widths = [font.getlength(ch) for ch in text]
        total = sum(widths) + self.L.d(spacing) * (len(text) - 1)
        px = self.L.x(x) - (total / 2 if anchor == "mm" else total if anchor == "rm" else 0)
        py = self.L.y(y)
        for ch, cw in zip(text, widths):
            self.d.text((px, py), ch, font=font, fill=fill, anchor="lm")
            px += cw + self.L.d(spacing)

    def runs(self, cx, y, parts, size, bold=True):
        """Centre a line made of differently coloured pieces: [(text, colour), ...]."""
        total = sum(self.tw(t, size, bold) for t, _ in parts)
        x = cx - total / 2
        for t, colour in parts:
            self.text(x, y, t, size, colour, bold)
            x += self.tw(t, size, bold)

    def wrapped(self, x, y, text, size, fill, width, line_height, bold=False, align="l", max_lines=8):
        """Word-wrapped text starting at (x, y) in a box `width` wide. Returns the number of lines."""
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if self.tw(trial, size, bold) <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines = (lines + ([line] if line else []))[:max_lines]
        for i, content in enumerate(lines):
            if align == "c":
                self.text(x + width / 2, y + i * line_height, content, size, fill, bold, "mm")
            else:
                self.text(x, y + i * line_height, content, size, fill, bold)
        return len(lines)

    # ---- images ----
    def paste(self, image, x, y):
        """Paste an RGBA picture with its top-left at design point (x, y)."""
        self.img.paste(image, (self.L.x(x), self.L.y(y)), image)

    def paste_centered(self, image, cx, top):
        self.img.paste(image, (self.L.x(cx) - image.width // 2, self.L.y(top)), image)

    def paste_rounded(self, image, x, y, w, h, radius):
        """Paste an RGB picture already sized to the design rectangle, with rounded corners."""
        x1, y1, x2, y2 = self.L.box(x, y, w, h)
        if image.size != (x2 - x1, y2 - y1):
            image = image.resize((x2 - x1, y2 - y1))
        mask = _rounded_mask(x2 - x1, y2 - y1, self.L.d(radius))
        self.img.paste(image, (x1, y1), mask)


_masks = {}
_widths = {}


def _rounded_mask(w, h, radius):
    key = (w, h, radius)
    if key not in _masks:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
        _masks[key] = mask
    return _masks[key]


def draw_card(canvas, x, y, w, h, accent=None, glow=None, radius=22, fill=theme.CARD):
    """A card with a soft shadow, an optional coloured top edge and an optional glow ring around it."""
    L = canvas.L
    x1, y1, x2, y2 = L.box(x, y, w, h)
    pad = L.d(44)
    size = (x2 - x1 + 2 * pad, y2 - y1 + 2 * pad)
    r = L.d(radius)

    def soft(blur, strength, colour, dy):
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([pad, pad, pad + x2 - x1, pad + y2 - y1], radius=r, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(L.d(blur))).point(lambda v: int(v * strength))
        canvas.img.paste(Image.new("RGB", size, colour), (x1 - pad, y1 - pad + L.d(dy)), mask)

    soft(13, 0.17, theme.INK, 10)
    if glow:
        soft(16, 0.55, glow, 0)
        ring = L.d(4)
        canvas.d.rounded_rectangle([x1 - ring, y1 - ring, x2 + ring, y2 + ring], radius=r + ring, fill=glow)
    if accent:
        canvas.d.rounded_rectangle([x1, y1, x2, y2], radius=r, fill=accent)
        canvas.d.rounded_rectangle([x1, y1 + L.d(6), x2, y2], radius=r, fill=fill)
    else:
        canvas.d.rounded_rectangle([x1, y1, x2, y2], radius=r, fill=fill, outline=theme.CARD_LINE, width=1)
