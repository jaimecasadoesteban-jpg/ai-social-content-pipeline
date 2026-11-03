"""Build a reel and run the automated QA judge on it.

Usage:
    python3 pipeline/reel.py build <reel_dir> --keyword DEMO   # HTML -> frames -> audio mix -> reel.mp4 -> judge
    python3 pipeline/reel.py judge <reel_dir> --keyword DEMO   # judge only (needs an existing build)

The folder holds reel.html and, for voiced reels, voice.wav (from voice.py).
The judge writes judge.json and exits with code 1 if any rule fails.
"""
import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUNDS = os.path.join(ROOT, "assets", "sounds")
FPS = 30
SAFE_AREA = dict(top=250, bottom=1500, left=40, right=1040)  # Instagram covers about 250 px on top and 420 px below
MAX_DURATION = 30.0
SECONDS_PER_WORD = 0.25
MIN_OPACITY = 0.6  # below this a text does not count as readable
STILL_DIFF = 0.8  # mean pixel difference under which the screen counts as still
SFX_GAIN = {"notify": 0.6, "send": 0.3, "done": 1.3}
MUSIC_WITH_VOICE, MUSIC_ALONE = 0.08, 0.5


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=True, **kwargs)


def load_json(*path):
    with open(os.path.join(*path), encoding="utf-8") as f:
        return json.load(f)


def build(folder, keyword):
    run(["node", os.path.join(ROOT, "pipeline", "render_frames.js"), os.path.join(folder, "reel.html"),
         os.path.join(folder, "frames"), "auto", str(FPS)])
    meta = load_json(folder, "meta.json")
    duration = meta["DUR"]
    voice = os.path.join(folder, "voice.wav")
    has_voice = os.path.exists(voice)
    cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", os.path.join(folder, "frames", "%05d.jpg")]
    labels, filters, index = [], [], 1
    if has_voice:
        cmd += ["-i", voice]
        filters.append(f"[{index}:a]aresample=44100,aformat=channel_layouts=stereo[v]")
        labels.append("[v]")
        index += 1
    cmd += ["-stream_loop", "-1", "-i", os.path.join(SOUNDS, "music.mp3")]
    music_gain = MUSIC_WITH_VOICE if has_voice else MUSIC_ALONE
    filters.append(f"[{index}:a]aresample=44100,atrim=0:{duration:.3f},volume={music_gain},afade=t=in:d=0.3,"
                   f"afade=t=out:st={max(0, duration - 1.0):.3f}:d=1.0,aformat=channel_layouts=stereo[m]")
    labels.append("[m]")
    index += 1
    for j, sfx in enumerate(meta.get("SFX", [])):
        cmd += ["-i", os.path.join(SOUNDS, sfx["s"] + ".mp3")]
        delay = int(sfx["t"] * 1000)
        filters.append(f"[{index}:a]aresample=44100,aformat=channel_layouts=stereo,volume={SFX_GAIN[sfx['s']]},"
                       f"adelay={delay}|{delay}[s{j}]")
        labels.append(f"[s{j}]")
        index += 1
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest,atrim=0:{duration:.3f},"
                   f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[a]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "slow",
            "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-t", f"{duration:.3f}",
            "-movflags", "+faststart", os.path.join(folder, "reel.mp4")]
    run(cmd)
    return judge(folder, keyword)


# --- Judge rules: pure functions, covered by tests/test_judge.py ---

def check_margins(audit, safe=SAFE_AREA):
    """Readable text must stay inside the area the Instagram interface does not cover."""
    first_bad = {}
    for frame in audit:
        for item in frame["items"]:
            if item["o"] < MIN_OPACITY:
                continue
            outside = (item["y"] < safe["top"] or item["y"] + item["h"] > safe["bottom"]
                       or item["x"] < safe["left"] or item["x"] + item["w"] > safe["right"])
            if outside:
                first_bad.setdefault(item["k"], (frame["t"], item))
    return [f"Outside safe area at {t:.1f} s: \"{i['txt'][:40]}\" (x {i['x']}-{i['x'] + i['w']}, y {i['y']}-{i['y'] + i['h']})"
            for t, i in first_bad.values()]


def check_read_time(audit, fps=FPS):
    """Each text must stay visible at least SECONDS_PER_WORD per word (the last frame stays on screen)."""
    seen = {}
    for frame in audit:
        for item in frame["items"]:
            if item["o"] >= MIN_OPACITY:
                seen.setdefault(item["k"], {"txt": item["txt"], "frames": []})["frames"].append(frame["t"])
    fails, last_t = [], audit[-1]["t"]
    for entry in seen.values():
        frames = entry["frames"]
        spans, start = [], frames[0]
        for prev, cur in zip(frames, frames[1:]):
            if cur - prev > 1.5 / fps:
                spans.append((start, prev))
                start = cur
        spans.append((start, frames[-1]))
        words = len(entry["txt"].split())
        needed = SECONDS_PER_WORD * words
        for a, b in spans:
            visible = b - a + 1 / fps
            if b < last_t - 1e-6 and visible + 1e-6 < needed:
                fails.append(f"Text visible {visible:.2f} s, needs {needed:.2f} s ({words} words): \"{entry['txt'][:50]}\" at {a:.1f} s")
    return fails


def visible_text(frame):
    return " ".join(i["txt"] for i in frame["items"] if i["o"] > MIN_OPACITY)


def check_keyword(audit, keyword):
    """The reel must end with the call-to-action keyword on screen."""
    return [] if keyword in visible_text(audit[-1]) else [f"Last frame does not show the keyword {keyword}"]


def check_first_frame(audit):
    """Frame 0 must already show the hook: it is what people see while scrolling."""
    return [] if len(visible_text(audit[0]).split()) >= 2 else ["Frame 0 does not show the hook"]


def check_shot_variety(scenes):
    """Two consecutive shots can never be of the same type."""
    return [f"Two consecutive shots of the same type: {a['type']} ({b['start']} s)" for a, b in zip(scenes, scenes[1:])
            if a["type"] == b["type"]]


def check_stillness(frames, fps=FPS):
    """`frames`: greyscale array (n, h, w). Fails if nothing moves for 2 s in a row."""
    step = 2 * fps
    for i in range(0, len(frames) - step):
        window = frames[i:i + step + 1]
        if np.abs(window - window[0]).mean(axis=(1, 2)).max() < STILL_DIFF:
            return [f"Screen still for 2 s starting at {i / fps:.1f} s"]
    return []


def check_silences(folder):
    """No silence over 0.5 s between the first and the last spoken word."""
    voice = os.path.join(folder, "voice.wav")
    if not os.path.exists(voice):
        return []
    words = load_json(folder, "words.json")
    first, last = words[0]["start"], words[-1]["end"]
    log = subprocess.run(["ffmpeg", "-v", "info", "-i", voice, "-af", "silencedetect=n=-40dB:d=0.5", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    fails = []
    for match in re.finditer(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", log):
        end, length = float(match.group(1)), float(match.group(2))
        if first < end - length and end < last:
            fails.append(f"Silence of {length:.2f} s at {end - length:.1f} s")
    return fails


def judge(folder, keyword):
    meta = load_json(folder, "meta.json")
    audit = load_json(folder, "audit.json")
    mp4 = os.path.join(folder, "reel.mp4")
    duration = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4],
                                    capture_output=True, text=True, check=True).stdout)
    frames_dir = os.path.join(folder, "frames")
    files = sorted(os.listdir(frames_dir))
    small = np.stack([np.asarray(Image.open(os.path.join(frames_dir, f)).convert("L").resize((108, 192)), dtype=np.float32)
                      for f in files])
    failures = []
    if duration > MAX_DURATION:
        failures.append(f"Lasts {duration:.1f} s (max {MAX_DURATION:.0f})")
    failures += check_silences(folder)
    failures += check_margins(audit)
    failures += check_read_time(audit)
    failures += check_keyword(audit, keyword)
    failures += check_first_frame(audit)
    failures += check_shot_variety(meta["scenes"])
    failures += check_stillness(small)

    events = meta.get("events", []) + [meta["DUR"]]
    warnings = [f"Nothing new enters between {a:.1f} and {b:.1f} s (only the camera moves)"
                for a, b in zip(events, events[1:]) if b - a > 2.05]
    report = {
        "failures": failures,
        "warnings": warnings,
        "duration": round(duration, 2),
        "frame_0": visible_text(audit[0])[:120],
        "shots": [f"{s['start']:.1f}-{s['end']:.1f} s {s['type']}" for s in meta["scenes"]],
    }
    # One-frame-per-second contact sheet, for the human or agent review of composition.
    run(["ffmpeg", "-y", "-v", "error", "-i", mp4, "-vf", "fps=1,scale=270:-1,tile=6x5:padding=6:color=white",
         "-frames:v", "1", os.path.join(folder, "contact_sheet.jpg")])
    with open(os.path.join(folder, "judge.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["build", "judge"])
    parser.add_argument("folder")
    parser.add_argument("--keyword", required=True, help="Call-to-action word the reel must end on")
    args = parser.parse_args()
    result = {"build": build, "judge": judge}[args.command](args.folder, args.keyword)
    sys.exit(1 if result["failures"] else 0)
