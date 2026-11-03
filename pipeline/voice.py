"""Generate a reel's voice-over and normalize its pauses.

Usage:
    python3 pipeline/voice.py <reel_dir> [--provider mock|elevenlabs]

Reads   <reel_dir>/script.txt (the text exactly as spoken).
Writes  voice.wav, voice.mp3, words.json ([{w, start, end}] in seconds, after pause
        normalization) and words.js (the same data, for the animation page).

Providers:
    mock        Offline placeholder: synthetic "speech" with realistic timing. No account needed.
    elevenlabs  Real text-to-speech. Needs ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID.

Pause rules: gaps between sentences (. ? ! :) end up between 0.25 s and 0.40 s (0.30 s target).
Any other gap between words is trimmed to 0.20 s at most.
"""
import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

import numpy as np

SAMPLE_RATE = 44100
LEAD_IN = 0.05  # the voice starts almost on frame 0
SENTENCE_MIN, SENTENCE_TARGET, SENTENCE_MAX = 0.25, 0.30, 0.40
WORD_GAP_MAX = 0.20
SILENCE_DB = -40
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_dotenv(path=None):
    """Load KEY=VALUE lines from .env without overriding the real environment."""
    path = path or os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def elevenlabs_tts(text):
    """Call ElevenLabs and return its response: base64 MP3 plus per-character timestamps."""
    key = os.environ.get("ELEVENLABS_API_KEY")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    if not key or not voice_id:
        sys.exit("Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID (see .env.example), or use --provider mock.")
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128",
        data=json.dumps({
            "text": text,
            "model_id": os.environ.get("ELEVENLABS_MODEL_ID", "eleven_v3"),
            "language_code": os.environ.get("TTS_LANGUAGE", "en"),
        }).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # 429 means too many concurrent requests: generate one voice at a time.
        sys.exit(f"ElevenLabs returned HTTP {error.code}. Nothing was generated.")


def mock_tts(text):
    """Offline stand-in that returns the same shape as ElevenLabs.

    It produces a low hum per word instead of speech, with long pauses after sentences, so the
    real pause-normalization and sync code runs on realistic input.
    """
    chars, starts, ends, chunks, t = [], [], [], [], 0.0
    silence = lambda s: np.zeros(int(s * SAMPLE_RATE), np.float32)
    for word in text.split():
        duration = min(0.08 + 0.055 * len(word), 0.70)
        n = int(duration * SAMPLE_RATE)
        time = np.arange(n) / SAMPLE_RATE
        envelope = np.sin(np.pi * np.arange(n) / n) ** 0.5
        tone = 0.6 * np.sin(2 * np.pi * 130 * time) + 0.3 * np.sin(2 * np.pi * 260 * time)
        chunks.append((0.22 * envelope * tone).astype(np.float32))
        per_char = duration / len(word)
        for i, c in enumerate(word):
            chars.append(c)
            starts.append(round(t + i * per_char, 3))
            ends.append(round(t + (i + 1) * per_char, 3))
        t += duration
        gap = 0.60 if word[-1] in ".?!:" else 0.16 if word[-1] in ",;" else 0.03
        chars.append(" ")
        starts.append(round(t, 3))
        ends.append(round(t + gap, 3))
        chunks.append(silence(gap))
        t += gap
    mp3 = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "-", "-b:a", "128k", "-f", "mp3", "-"],
        input=np.concatenate(chunks).tobytes(), capture_output=True, check=True,
    ).stdout
    return {
        "audio_base64": base64.b64encode(mp3).decode(),
        "alignment": {"characters": chars, "character_start_times_seconds": starts, "character_end_times_seconds": ends},
    }


def words_from_alignment(alignment):
    """Group per-character timestamps into words."""
    words, current = [], None
    for c, start, end in zip(alignment["characters"], alignment["character_start_times_seconds"],
                             alignment["character_end_times_seconds"]):
        if c.isspace():
            if current:
                words.append(current)
                current = None
            continue
        if current is None:
            current = {"w": "", "start": start, "end": end}
        current["w"] += c
        current["end"] = end
    if current:
        words.append(current)
    return words


def normalize_pauses(audio, words, sr=SAMPLE_RATE):
    """Rewrite the audio so every pause follows the rules, and remap word timings to match.

    Returns (new_audio, new_words). Works on real measured silence, not on the provider's timing.
    """
    # 1) Measure silences: 10 ms windows below the threshold.
    hop = int(0.01 * sr)
    n = len(audio) // hop
    rms = np.sqrt(np.mean(audio[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    silent = 20 * np.log10(rms) < SILENCE_DB
    runs, i = [], 0
    while i < n:
        if silent[i]:
            j = i
            while j < n and silent[j]:
                j += 1
            runs.append((i * hop, j * hop))
            i = j
        else:
            i += 1

    # 2) Decide which silences end a sentence.
    sentence_ends = [w["end"] for w in words if w["w"][-1] in ".?!:"]
    first_voice = runs[0][1] if runs and runs[0][0] == 0 else 0
    last_voice = runs[-1][0] if runs and runs[-1][1] >= n * hop else len(audio)
    candidates = [r for r in runs if r[0] > 0 and r[1] < n * hop and (r[1] - r[0]) / sr >= 0.12]
    sentence_runs = set()
    for end in sentence_ends:
        near = [r for r in candidates if r[1] / sr > end - 0.3 and r[0] / sr < end + 0.6]
        if not near:  # two sentences glued together: open a pause at the quietest nearby point
            small = [r for r in runs if r[1] / sr > end - 0.2 and r[0] / sr < end + 0.3 and r[0] > 0]
            if small:
                near = [max(small, key=lambda r: r[1] - r[0])]
            else:
                lo, hi = int((end - 0.1) * sr) // hop, int((end + 0.15) * sr) // hop
                if lo >= hi or lo >= n:  # last word: nothing to open
                    continue
                k = lo + int(np.argmin(rms[lo:hi]))
                near = [(k * hop, k * hop)]
            candidates.append(near[0])
        sentence_runs.add(max(near, key=lambda r: r[1] - r[0]))
    candidates = sorted(set(candidates))

    cuts = []  # (start, end, wanted length in samples)
    for a, b in candidates:
        duration = (b - a) / sr
        if (a, b) in sentence_runs:
            wanted = duration if SENTENCE_MIN <= duration <= SENTENCE_MAX else SENTENCE_TARGET
        else:
            wanted = min(duration, WORD_GAP_MAX)
        if abs(wanted - duration) > 0.01:
            cuts.append((a, b, int(wanted * sr)))

    # 3) Rebuild the audio and track how time moves.
    out = [np.zeros(int(LEAD_IN * sr), np.float32)]
    pos = max(0, first_voice - int(0.02 * sr))
    time_map = [(pos / sr, LEAD_IN)]  # (original time, new time)
    t_out = LEAD_IN
    for a, b, wanted in cuts:
        out.append(audio[pos:a])
        t_out += (a - pos) / sr
        time_map.append((a / sr, t_out))
        half = min(wanted // 2, (b - a) // 2)
        gap = np.concatenate([audio[a:a + half], np.zeros(max(0, wanted - 2 * half), np.float32), audio[b - half:b]])
        out.append(gap)
        t_out += len(gap) / sr
        time_map.append((b / sr, t_out))
        pos = b
    stop = min(len(audio), last_voice + int(0.25 * sr))
    tail = audio[pos:stop].copy()
    fade = min(len(tail), int(0.12 * sr))
    if fade:
        tail[-fade:] *= np.linspace(1, 0, fade)
    out.append(tail)
    time_map.append((stop / sr, t_out + len(tail) / sr))

    old_times = np.array([m[0] for m in time_map])
    new_times = np.array([m[1] for m in time_map])
    remap = lambda t: round(float(np.interp(t, old_times, new_times)), 3)
    new_words = [{"w": w["w"], "start": remap(w["start"]), "end": remap(w["end"])} for w in words]
    return np.concatenate(out), new_words


def get_raw_voice(folder, text, provider):
    """Reuse the saved response while script and provider are unchanged, so paid calls are not repeated."""
    raw_path = os.path.join(folder, "voice_raw.json")
    fingerprint = hashlib.sha256(f"{provider}\n{text}".encode()).hexdigest()
    if os.path.exists(raw_path):
        with open(raw_path) as f:
            saved = json.load(f)
        if saved.get("fingerprint") == fingerprint:
            return saved
    data = {"mock": mock_tts, "elevenlabs": elevenlabs_tts}[provider](text)
    data["fingerprint"] = fingerprint
    with open(raw_path, "w") as f:
        json.dump(data, f)
    return data


def main(folder, provider):
    with open(os.path.join(folder, "script.txt"), encoding="utf-8") as f:
        text = f.read().strip()
    data = get_raw_voice(folder, text, provider)
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"],
        input=base64.b64decode(data["audio_base64"]), capture_output=True, check=True,
    ).stdout
    audio, words = normalize_pauses(np.frombuffer(pcm, dtype=np.float32), words_from_alignment(data["alignment"]))
    wav = os.path.join(folder, "voice.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "-", wav],
                   input=audio.astype(np.float32).tobytes(), check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-b:a", "192k", os.path.join(folder, "voice.mp3")], check=True)
    with open(os.path.join(folder, "words.json"), "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=0)
    with open(os.path.join(folder, "words.js"), "w", encoding="utf-8") as f:
        f.write("window.WORDS = " + json.dumps(words, ensure_ascii=False) + ";\n")
    print(f"{folder}: {len(words)} words, {len(audio) / SAMPLE_RATE:.2f} s ({provider})")


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder")
    parser.add_argument("--provider", choices=["mock", "elevenlabs"], default=os.environ.get("VOICE_PROVIDER", "mock"))
    args = parser.parse_args()
    main(args.folder, args.provider)
