"""Drawing in design units (1280 x 720). The canvas scales everything to the real frame size.

Pillow does not smooth the edges of shapes, so every rounded shape, circle, arc and line is drawn through an
anti-aliased mask: drawn at several times the size, then shrunk.
"""
import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from ui import theme
from ui.theme import get_font

SUPERSAMPLE = 4


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


_masks = {}
_rings = {}
_widths = {}


def clear_caches():
    _masks.clear()
    _rings.clear()
    _widths.clear()


def aa_mask(w, h, radius):
    """A smooth-edged rounded rectangle, as a greyscale mask."""
    key = (w, h, radius)
    if key not in _masks:
        big = Image.new("L", (w * SUPERSAMPLE, h * SUPERSAMPLE), 0)
        ImageDraw.Draw(big).rounded_rectangle([0, 0, w * SUPERSAMPLE - 1, h * SUPERSAMPLE - 1],
                                              radius=radius * SUPERSAMPLE, fill=255)
        _masks[key] = big.resize((w, h), Image.BOX)
    return _masks[key]


def ring_mask(w, h, radius, width):
    """Just the outline of a rounded rectangle."""
    key = (w, h, radius, width)
    if key not in _rings:
        inner = Image.new("L", (w, h), 0)
        inner.paste(aa_mask(w - 2 * width, h - 2 * width, max(0, radius - width)), (width, width))
        _rings[key] = ImageChops.subtract(aa_mask(w, h, radius), inner)
    return _rings[key]


class Canvas:
    def __init__(self, image, layout):
        self.img = image
        self.L = layout
        self.d = ImageDraw.Draw(image)

    # ---- shapes ----
    def rect(self, x, y, w, h, fill=None, outline=None, width=1, radius=0):
        x1, y1, x2, y2 = self.L.box(x, y, w, h)
        pw, ph = max(2, x2 - x1), max(2, y2 - y1)
        if not radius:
            self.d.rectangle((x1, y1, x1 + pw - 1, y1 + ph - 1), fill=fill, outline=outline,
                             width=self.L.d(width) if outline else 0)
            return
        r = min(self.L.d(radius), pw // 2, ph // 2)
        if outline and fill is None:
            self.img.paste(outline, (x1, y1), ring_mask(pw, ph, r, self.L.d(width)))
            return
        self.img.paste(outline or fill, (x1, y1), aa_mask(pw, ph, r))
        if outline and fill is not None:
            lw = self.L.d(width)
            self.img.paste(fill, (x1 + lw, y1 + lw), aa_mask(pw - 2 * lw, ph - 2 * lw, max(0, r - lw)))

    def _paint(self, colour, bounds, draw_fn, ss=3):
        """Draw a shape smoothly: `draw_fn(draw, to_big, ss)` draws in a layer `ss` times larger than the screen."""
        x0 = max(0, int(math.floor(bounds[0])) - 2)
        y0 = max(0, int(math.floor(bounds[1])) - 2)
        x1 = min(self.img.width, int(math.ceil(bounds[2])) + 2)
        y1 = min(self.img.height, int(math.ceil(bounds[3])) + 2)
        if x1 <= x0 or y1 <= y0:
            return
        mask = Image.new("L", ((x1 - x0) * ss, (y1 - y0) * ss), 0)
        draw_fn(ImageDraw.Draw(mask), lambda px, py: ((px - x0) * ss, (py - y0) * ss), ss)
        self.img.paste(colour, (x0, y0), mask.resize((x1 - x0, y1 - y0), Image.BOX))

    def circle(self, cx, cy, r, fill=None, outline=None, width=1):
        L = self.L
        px, py, pr = L.x(cx), L.y(cy), r * L.s
        bounds = (px - pr, py - pr, px + pr, py + pr)

        def disc(radius, value):
            return lambda d, tf, ss: d.ellipse([*tf(px - radius, py - radius), *tf(px + radius, py + radius)], fill=value)

        if outline and fill is None:
            inner = pr - L.d(width)
            self._paint(outline, bounds, lambda d, tf, ss: (disc(pr, 255)(d, tf, ss), disc(inner, 0)(d, tf, ss)))
            return
        self._paint(outline or fill, bounds, disc(pr, 255))
        if outline and fill is not None:
            self._paint(fill, bounds, disc(pr - L.d(width), 255))

    def arc(self, cx, cy, r, start, end, fill, width):
        L = self.L
        px, py, pr, lw = L.x(cx), L.y(cy), r * L.s, L.d(width)
        self._paint(fill, (px - pr - 1, py - pr - 1, px + pr + 1, py + pr + 1),
                    lambda d, tf, ss: d.arc([*tf(px - pr, py - pr), *tf(px + pr, py + pr)], start, end, fill=255, width=lw * ss))

    def pie(self, cx, cy, r, start, end, fill):
        L = self.L
        px, py, pr = L.x(cx), L.y(cy), r * L.s
        self._paint(fill, (px - pr - 1, py - pr - 1, px + pr + 1, py + pr + 1),
                    lambda d, tf, ss: d.pieslice([*tf(px - pr, py - pr), *tf(px + pr, py + pr)], start, end, fill=255))

    def line(self, points, fill, width=1):
        L = self.L
        pts = [(L.x(px), L.y(py)) for px, py in points]
        lw = max(1.0, width * L.s)

        def draw(d, tf, ss):
            big = [tf(*p) for p in pts]
            d.line(big, fill=255, width=round(lw * ss), joint="curve")
            for bx, by in big:
                d.ellipse([bx - lw * ss / 2, by - lw * ss / 2, bx + lw * ss / 2, by + lw * ss / 2], fill=255)

        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self._paint(fill, (min(xs) - lw, min(ys) - lw, max(xs) + lw, max(ys) + lw), draw)

    def polygon(self, points, fill):
        L = self.L
        pts = [(L.x(px), L.y(py)) for px, py in points]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self._paint(fill, (min(xs), min(ys), max(xs), max(ys)),
                    lambda d, tf, ss: d.polygon([tf(*p) for p in pts], fill=255))

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

    def glyph_text(self, x, y, text, size, fill, bold=False):
        """Text whose letters (not the line around them) are centred on (x, y), for big numbers."""
        font = self.font(size, bold)
        left, top, right, bottom = font.getbbox(text, anchor="ls")
        self.d.text((self.L.x(x) - (left + right) / 2, self.L.y(y) - (top + bottom) / 2), text, font=font, fill=fill, anchor="ls")

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

    def wrap_lines(self, text, size, width, bold=False):
        """Break `text` into lines no wider than `width` design units."""
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if self.tw(trial, size, bold) <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        return lines + ([line] if line else [])

    def wrapped(self, x, y, text, size, fill, width, line_height, bold=False, align="l", max_lines=8):
        """Word-wrapped text starting at (x, y) in a box `width` wide. Returns the number of lines."""
        lines = self.wrap_lines(text, size, width, bold)
        if len(lines) > max_lines:   # never stop mid-sentence without saying so
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip(" .,;") + "…"
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
        """Paste an RGB picture with smooth rounded corners; it is resized to the design rectangle if needed."""
        x1, y1, x2, y2 = self.L.box(x, y, w, h)
        if image.size != (x2 - x1, y2 - y1):
            image = image.resize((x2 - x1, y2 - y1))
        self.img.paste(image, (x1, y1), aa_mask(x2 - x1, y2 - y1, self.L.d(radius)))


def draw_card(canvas, x, y, w, h, accent=None, glow=None, radius=22, fill=theme.CARD):
    """A card with a soft shadow, an optional coloured top edge and an optional glow ring around it."""
    L = canvas.L
    x1, y1, x2, y2 = L.box(x, y, w, h)
    cw, ch = x2 - x1, y2 - y1
    pad = L.d(44)
    size = (cw + 2 * pad, ch + 2 * pad)
    r = L.d(radius)

    def soft(blur, strength, colour, dy):
        mask = Image.new("L", size, 0)
        mask.paste(aa_mask(cw, ch, r), (pad, pad))
        mask = mask.filter(ImageFilter.GaussianBlur(L.d(blur))).point(lambda v: int(v * strength))
        canvas.img.paste(Image.new("RGB", size, colour), (x1 - pad, y1 - pad + L.d(dy)), mask)

    soft(13, 0.17, theme.INK, 10)
    if glow:
        soft(16, 0.55, glow, 0)
        ring = L.d(4)
        canvas.img.paste(glow, (x1 - ring, y1 - ring), aa_mask(cw + 2 * ring, ch + 2 * ring, r + ring))
    if accent:
        edge = L.d(6)
        canvas.img.paste(accent, (x1, y1), aa_mask(cw, ch, r).crop((0, 0, cw, r + edge * 2)))
        canvas.img.paste(fill, (x1, y1 + edge), aa_mask(cw, ch - edge, r))
    else:
        canvas.img.paste(theme.CARD_LINE, (x1, y1), aa_mask(cw, ch, r))
        canvas.img.paste(fill, (x1 + 1, y1 + 1), aa_mask(cw - 2, ch - 2, max(0, r - 1)))
