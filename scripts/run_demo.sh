#!/usr/bin/env bash
# Builds the whole demo week offline: no accounts, API keys or private systems.
set -euo pipefail
cd "$(dirname "$0")/.."

for tool in python3 node ffmpeg ffprobe; do
  command -v "$tool" >/dev/null || { echo "Missing dependency: $tool (see README, Setup Instructions)"; exit 1; }
done
PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && PY=.venv/bin/python

WEEK=demo/week
KEYWORD=DEMO

echo "==> 1/5 Sounds"
"$PY" pipeline/make_sounds.py

echo "==> 2/5 Voice (provider: ${VOICE_PROVIDER:-mock})"
"$PY" pipeline/voice.py "$WEEK/monday"

echo "==> 3/5 Reels and QA judge (a few minutes: every frame is rendered in headless Chrome)"
"$PY" pipeline/reel.py build "$WEEK/monday" --keyword "$KEYWORD"
"$PY" pipeline/reel.py build "$WEEK/tuesday" --keyword "$KEYWORD"

echo "==> 4/5 Carousel and covers"
node pipeline/export_slides.js "$WEEK/tuesday/carousel.html" "$WEEK/tuesday/carousel"
node pipeline/export_slides.js "$WEEK/covers.html" "$WEEK/covers"

echo "==> 5/5 Copy validation and review page"
"$PY" pipeline/assemble.py "$WEEK"

echo
echo "Done. Open $WEEK/output/review.html"
