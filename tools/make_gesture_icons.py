"""Cuts the rock, paper and scissors hands out of the banner artwork into transparent PNGs.

Usage: python tools/make_gesture_icons.py <banner.jpg> [output folder]

Each hand has a white sticker-style outline. Flooding the background from outside the
outline and keeping everything it can't reach gives the hand, and the white outline stays.
All three icons are turned upright with the wrist at the bottom, and the wrist fades out.
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image

# Crop boxes as fractions of the 2000 x 1125 preview of the banner artwork: x1, y1, x2, y2.
# Each box avoids the printed words, and its edge cuts the arm, where the outline meets the border.
# `seeds` are corners that are plain background, `turn` is the rotation that points fingers up.
HANDS = {
    "rock":     dict(box=(290, 760, 510, 1062), seeds=["tl", "tr"], turn=0),
    "paper":    dict(box=(825, 175, 1277, 385), seeds=["tl", "bl"], turn=-90),
    "scissors": dict(box=(722, 735, 1160, 995), seeds=["tr", "br", "bl"], turn=90),
}
PREVIEW_WIDTH = 2000
OUTLINE_MIN_CHANNEL = 215
ICON_HEIGHT = 480
ARM_FADE = 0.22


def seed_points(w, h, names):
    corners = {"tl": (2, 2), "tr": (w - 3, 2), "bl": (2, h - 3), "br": (w - 3, h - 3)}
    return [corners[n] for n in names]


def cut_out(crop_rgb, seeds):
    h, w = crop_rgb.shape[:2]
    outline = (crop_rgb.min(axis=2) >= OUTLINE_MIN_CHANNEL).astype(np.uint8)
    outline = cv2.dilate(outline, np.ones((3, 3), np.uint8))  # seal gaps in the anti-aliased line

    # Flood the background: 0 = open to fill, 1 = barrier. Whatever stays 0 and unreached is the hand.
    barrier = outline.copy()
    flooded = np.zeros((h + 2, w + 2), np.uint8)
    flooded[1:-1, 1:-1] = barrier
    for x, y in seeds:
        if flooded[y + 1, x + 1] == 0:
            cv2.floodFill(np.zeros((h, w), np.uint8), flooded, (x, y), 1, flags=4 | cv2.FLOODFILL_MASK_ONLY | (1 << 8))
    reached = flooded[1:-1, 1:-1] == 1
    reached &= barrier == 0
    hand = (~reached).astype(np.uint8) * 255

    # Keep only the largest piece: drops stray sparkles and any lettering
    count, labels, stats, _ = cv2.connectedComponentsWithStats(hand, connectivity=4)
    if count > 1:
        biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        hand = np.where(labels == biggest, 255, 0).astype(np.uint8)

    hand = cv2.erode(hand, np.ones((3, 3), np.uint8))          # drop the coloured fringe
    return cv2.GaussianBlur(hand, (0, 0), 1.2)                 # soft anti-aliased edge


def make_icon(source, name, spec):
    scale = source.width / PREVIEW_WIDTH
    x1, y1, x2, y2 = (int(v * scale) for v in spec["box"])
    crop = np.array(source.crop((x1, y1, x2, y2)))
    alpha = cut_out(crop, seed_points(crop.shape[1], crop.shape[0], spec["seeds"]))

    icon = Image.fromarray(np.dstack([crop, alpha]), "RGBA")
    icon = icon.crop(icon.getbbox())
    if spec["turn"]:
        icon = icon.rotate(spec["turn"], expand=True)
    icon = icon.resize((round(icon.width * ICON_HEIGHT / icon.height), ICON_HEIGHT), Image.LANCZOS)

    # Fade the wrist so the cut end of the arm never shows
    fade = np.ones(icon.height, np.float32)
    start = int(icon.height * (1 - ARM_FADE))
    fade[start:] = np.linspace(1, 0, icon.height - start)
    pixels = np.array(icon)
    pixels[:, :, 3] = (pixels[:, :, 3] * fade[:, None]).astype(np.uint8)
    return Image.fromarray(pixels, "RGBA")


def main():
    source_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join("assets", "gestures")
    os.makedirs(out_dir, exist_ok=True)
    source = Image.open(source_path).convert("RGB")
    for name, spec in HANDS.items():
        icon = make_icon(source, name, spec)
        icon.save(os.path.join(out_dir, f"{name}.png"), optimize=True)
        print(f"{name}: {icon.size[0]} x {icon.size[1]}")


if __name__ == "__main__":
    main()
