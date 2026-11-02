import io
import wave

import pytest

from game import sound
from game.sound import SOUNDS, Sounds, make_wav


@pytest.mark.parametrize("name", sorted(SOUNDS))
def test_every_sound_is_a_valid_wav_of_the_right_length(name):
    with wave.open(io.BytesIO(make_wav(SOUNDS[name]))) as wav:
        expected = sum(int(sound.RATE * ms / 1000) for _, ms in SOUNDS[name])
        assert wav.getnframes() == expected and wav.getnchannels() == 1 and wav.getsampwidth() == 2


def test_sounds_play_through_winsound_without_waiting(monkeypatch):
    calls = []

    class FakeWinsound:
        SND_MEMORY, SND_ASYNC = 4, 1
        PlaySound = staticmethod(lambda data, flags: calls.append((len(data), flags)))

    monkeypatch.setattr(sound, "winsound", FakeWinsound)
    Sounds().play("win")
    assert len(calls) == 1 and calls[0][1] == 5


def test_a_disabled_or_unknown_sound_stays_silent(monkeypatch):
    calls = []

    class FakeWinsound:
        SND_MEMORY, SND_ASYNC = 4, 1
        PlaySound = staticmethod(lambda data, flags: calls.append(1))

    monkeypatch.setattr(sound, "winsound", FakeWinsound)
    Sounds(enabled=False).play("win")
    Sounds().play("no such sound")
    assert calls == []


def test_without_winsound_nothing_breaks(monkeypatch):
    monkeypatch.setattr(sound, "winsound", None)
    Sounds().play("win")
