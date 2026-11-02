"""Short sounds, made in code so no audio files are needed. They play on Windows (winsound); elsewhere the game is silent."""
import io
import math
import struct
import wave

try:
    import winsound
except ImportError:  # not Windows
    winsound = None

RATE = 22050

# Each sound is a list of (frequency in Hz, length in ms)
SOUNDS = {
    "tick0": [(660, 70)],
    "tick1": [(784, 70)],
    "tick2": [(988, 70)],
    "win": [(659, 90), (784, 90), (1047, 220)],
    "lose": [(392, 150), (311, 280)],
    "draw": [(523, 110), (523, 170)],
    "missed": [(220, 280)],
    "passed": [(784, 80), (1047, 180)],
    "report": [(523, 100), (659, 100), (784, 100), (1047, 320)],
}


def make_wav(notes, volume=0.45):
    """A mono 16-bit WAV, as bytes, of the notes one after another."""
    samples = []
    for frequency, milliseconds in notes:
        count = int(RATE * milliseconds / 1000)
        fade = max(1, int(RATE * 0.008))   # a short fade in and out avoids clicks
        for i in range(count):
            envelope = min(1.0, i / fade, (count - 1 - i) / fade)
            samples.append(int(32767 * volume * envelope * math.sin(2 * math.pi * frequency * i / RATE)))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return buffer.getvalue()


class Sounds:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._wavs = {}

    def play(self, name):
        """Start a sound without waiting for it. A new sound cuts off the one still playing."""
        if not self.enabled or winsound is None or name not in SOUNDS:
            return
        if name not in self._wavs:
            self._wavs[name] = make_wav(SOUNDS[name])
        try:
            winsound.PlaySound(self._wavs[name], winsound.SND_MEMORY | winsound.SND_ASYNC)
        except RuntimeError:
            pass
