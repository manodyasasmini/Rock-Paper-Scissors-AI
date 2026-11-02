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
        SND_FILENAME, SND_ASYNC = 131072, 1
        PlaySound = staticmethod(lambda data, flags: calls.append((data, flags)))

    monkeypatch.setattr(sound, "winsound", FakeWinsound)
    Sounds().play("win")
    path, flags = calls[0]
    assert len(calls) == 1 and flags == 131073 and path.endswith("win.wav")
    with wave.open(path) as wav:                      # the file really is a playable WAV
        assert wav.getnframes() > 0


def test_a_disabled_or_unknown_sound_stays_silent(monkeypatch):
    calls = []

    class FakeWinsound:
        SND_FILENAME, SND_ASYNC = 131072, 1
        PlaySound = staticmethod(lambda data, flags: calls.append(1))

    monkeypatch.setattr(sound, "winsound", FakeWinsound)
    Sounds(enabled=False).play("win")
    Sounds().play("no such sound")
    assert calls == []


def test_without_winsound_nothing_breaks(monkeypatch):
    monkeypatch.setattr(sound, "winsound", None)
    Sounds().play("win")


def test_the_real_windows_call_accepts_the_files():
    """The first version used SND_MEMORY with SND_ASYNC, which Windows rejects, and the error was hidden."""
    if sound.winsound is None:
        pytest.skip("not Windows")
    path = Sounds()._path("tick0")
    sound.winsound.PlaySound(None, sound.winsound.SND_PURGE)
    sound.winsound.PlaySound(path, sound.winsound.SND_FILENAME | sound.winsound.SND_ASYNC)   # must not raise
    sound.winsound.PlaySound(None, sound.winsound.SND_PURGE)


def test_a_failing_player_prints_one_warning_instead_of_hiding_the_problem(monkeypatch, capsys):
    class Broken:
        SND_FILENAME, SND_ASYNC = 131072, 1

        @staticmethod
        def PlaySound(data, flags):
            raise RuntimeError("nope")

    monkeypatch.setattr(sound, "winsound", Broken)
    player = Sounds()
    player.play("win")
    player.play("lose")
    assert capsys.readouterr().out.count("WARNING: sound could not play") == 1
