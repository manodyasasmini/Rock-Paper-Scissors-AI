"""Fake hands, so tests need no camera."""

FRAME_W, FRAME_H = 1280, 720


def make_hand(cx=640, cy=360, palm=150, gesture="PAPER", frame_w=FRAME_W, frame_h=FRAME_H):
    """21 normalised landmarks for an upright hand. The wrist is `palm` pixels from the middle knuckle."""
    pts = {0: (cx, cy + palm / 2)}
    y0 = cy - palm / 2
    pts[1] = (cx - 0.4 * palm, cy + 0.3 * palm)
    pts[2] = (cx - 0.7 * palm, cy)
    pts[3] = (cx - 0.9 * palm, cy - 0.25 * palm)
    pts[4] = (cx - 1.0 * palm, cy - 0.45 * palm)

    extended = {"ROCK": [], "PAPER": [0, 1, 2, 3], "SCISSORS": [0, 1]}[gesture]
    for finger, mcp_x in enumerate((cx - 0.45 * palm, cx, cx + 0.4 * palm, cx + 0.75 * palm)):
        base = 5 + 4 * finger
        pts[base] = (mcp_x, y0)
        if finger in extended:
            pts[base + 1] = (mcp_x, y0 - 0.45 * palm)
            pts[base + 2] = (mcp_x, y0 - 0.70 * palm)
            pts[base + 3] = (mcp_x, y0 - 0.95 * palm)
        else:
            pts[base + 1] = (mcp_x, y0 - 0.35 * palm)
            pts[base + 2] = (mcp_x, y0 - 0.05 * palm)
            pts[base + 3] = (mcp_x, y0 + 0.10 * palm)
    return [(pts[i][0] / frame_w, pts[i][1] / frame_h) for i in range(21)]


def rotate(landmarks, quarter_turns):
    """Rotate normalised landmarks about (0.5, 0.5) by 90 degree steps."""
    out = landmarks
    for _ in range(quarter_turns % 4):
        out = [(1 - y, x) for x, y in out]
    return out
