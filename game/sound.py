"""Short sounds, made in code so no audio files are needed. They play on Windows (winsound); elsewhere the game is silent."""
import io
import math
import os
import struct
import tempfile
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
    "win": [(523, 70), (659, 70), (784, 70), (1047, 70), (784, 60), (1047, 320)],
    "lose": [(392, 150), (311, 280)],
    "draw": [(523, 110), (523, 170)],
    "missed": [(220, 280)],
    "passed": [(784, 80), (1047, 180)],
    "report": [(523, 100), (659, 100), (784, 100), (1047, 320)],
}


# Other win sounds to choose from (see tools/preview_win_sounds.py). Copy one into SOUNDS["win"] to use it.
WIN_OPTIONS = {
    "A: quick rising run": [(523, 70), (659, 70), (784, 70), (1047, 70), (784, 60), (1047, 320)],
    "B: two bright notes": [(784, 110), (1175, 380)],
    "C: gentle chime": [(1319, 120), (1568, 120), (2093, 420)],
    "D: low and warm": [(392, 130), (523, 130), (659, 330)],
}


def make_wav(notes, volume=0.45):
    """A mono 16-bit WAV, as bytes, of the notes one after another."""
    samples = []
    for frequency, milliseconds in notes:
        count = int(RATE * milliseconds / 1000)
        fade = max(1, int(RATE * 0.008))   # a short fade in and out avoids clicks
        for i in range(count):
            envelope = min(1.0, i / fade, (count - 1 - i) / fade)
            tone = math.sin(2 * math.pi * frequency * i / RATE) + 0.25 * math.sin(4 * math.pi * frequency * i / RATE)   # a little overtone, so it is not a bare beep
            samples.append(int(32767 * volume * envelope * tone / 1.25))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return buffer.getvalue()


class Sounds:
    """Plays the sounds. Windows cannot play from memory without waiting, so each sound is saved once as a small
    WAV file in a temporary folder and played from there without waiting."""

    def __init__(self, enabled=True):
        self.enabled = enabled
        self._folder = None
        self._files = {}

    def _path(self, name):
        if name not in self._files:
            if self._folder is None:
                self._folder = tempfile.mkdtemp(prefix="rps-sounds-")
            path = os.path.join(self._folder, f"{name}.wav")
            with open(path, "wb") as f:
                f.write(make_wav(SOUNDS[name]))
            self._files[name] = path
        return self._files[name]

    def play(self, name):
        """Start a sound without waiting for it. A new sound cuts off the one still playing."""
        if not self.enabled or winsound is None or name not in SOUNDS:
            return
        try:
            winsound.PlaySound(self._path(name), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except (RuntimeError, OSError) as error:
            if not getattr(self, "_warned", False):
                print(f"WARNING: sound could not play: {error}")
                self._warned = True
