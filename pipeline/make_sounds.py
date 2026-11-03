"""Synthesize the music bed and sound effects, so the repo ships no third-party audio.

Usage: python3 pipeline/make_sounds.py
Writes assets/sounds/{music,notify,send,done}.mp3.
"""
import os
import subprocess

import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sounds")


def tone(freq, seconds, decay=6.0, gain=0.5):
    t = np.arange(int(seconds * SR)) / SR
    return gain * np.sin(2 * np.pi * freq * t) * np.exp(-decay * t)


def sequence(*parts):
    """(start seconds, signal) pairs, mixed into a 1-second clip."""
    clip = np.zeros(SR)
    for start, signal in parts:
        i = int(start * SR)
        end = min(len(clip), i + len(signal))
        clip[i:end] += signal[:end - i]
    return clip


def music(seconds=32.0):
    """Slow ambient chord loop: Am, F, C, G."""
    t = np.arange(int(seconds * SR)) / SR
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (146.83, 196.0, 246.94)]
    bar = 4.0
    out = np.zeros_like(t)
    for i in range(int(seconds / bar)):
        mask = (t >= i * bar) & (t < (i + 1) * bar)
        local = t[mask] - i * bar
        swell = np.sin(np.pi * local / bar) ** 0.8
        for freq in chords[i % 4]:
            out[mask] += swell * (np.sin(2 * np.pi * freq * local) + 0.3 * np.sin(2 * np.pi * 2 * freq * local))
    return 0.8 * out / np.max(np.abs(out))


def save(name, signal):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", "-b:a", "128k",
                    os.path.join(OUT, name + ".mp3")], input=signal.astype(np.float32).tobytes(), check=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    save("music", music())
    save("notify", sequence((0, tone(880, 0.3)), (0.12, tone(1174.66, 0.4))))
    save("send", sequence((0, tone(600, 0.15, 14, 0.4)), (0.05, tone(900, 0.18, 14, 0.4))))
    save("done", sequence((0, tone(523.25, 0.3)), (0.1, tone(659.25, 0.3)), (0.2, tone(783.99, 0.5))))
    print("Sounds written to", OUT)
