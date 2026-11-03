import base64
import json
import shutil

import numpy as np
import pytest

import voice

SR = voice.SAMPLE_RATE


def synth(segments):
    """segments: list of (word, seconds, gap after). Returns audio and ElevenLabs-style words."""
    chunks, words, t = [], [], 0.0
    for word, dur, gap in segments:
        chunks.append(0.3 * np.sin(2 * np.pi * 200 * np.arange(int(dur * SR)) / SR).astype(np.float32))
        chunks.append(np.zeros(int(gap * SR), np.float32))
        words.append({"w": word, "start": t, "end": t + dur})
        t += dur + gap
    return np.concatenate(chunks), words


def gaps(words):
    return [round(b["start"] - a["end"], 2) for a, b in zip(words, words[1:])]


def test_long_sentence_pause_shrinks_to_target():
    audio, words = synth([("One.", 0.5, 1.2), ("Two.", 0.5, 0.0)])
    _, new = voice.normalize_pauses(audio, words)
    assert voice.SENTENCE_MIN <= gaps(new)[0] <= voice.SENTENCE_MAX


def test_short_sentence_pause_grows_to_target():
    audio, words = synth([("One.", 0.5, 0.15), ("Two.", 0.5, 0.0)])
    _, new = voice.normalize_pauses(audio, words)
    assert voice.SENTENCE_MIN <= gaps(new)[0] <= voice.SENTENCE_MAX


def test_sentence_pause_in_range_is_kept():
    audio, words = synth([("One.", 0.5, 0.35), ("Two.", 0.5, 0.0)])
    _, new = voice.normalize_pauses(audio, words)
    assert gaps(new)[0] == pytest.approx(0.35, abs=0.02)


def test_pause_inside_a_sentence_is_capped():
    audio, words = synth([("one", 0.5, 0.6), ("two.", 0.5, 0.0)])
    _, new = voice.normalize_pauses(audio, words)
    assert gaps(new)[0] <= voice.WORD_GAP_MAX + 0.01


def test_audio_length_matches_remapped_timings():
    audio, words = synth([("One.", 0.5, 1.0), ("two", 0.4, 0.5), ("three.", 0.5, 0.0)])
    out, new = voice.normalize_pauses(audio, words)
    assert new[0]["start"] == pytest.approx(voice.LEAD_IN, abs=0.03)
    assert all(w["start"] < w["end"] for w in new)
    assert new[-1]["end"] <= len(out) / SR + 0.01


def test_words_from_alignment_groups_characters():
    alignment = {"characters": list("hi yo"), "character_start_times_seconds": [0, .1, .2, .3, .4],
                 "character_end_times_seconds": [.1, .2, .3, .4, .5]}
    assert voice.words_from_alignment(alignment) == [{"w": "hi", "start": 0, "end": .2}, {"w": "yo", "start": .3, "end": .5}]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_mock_provider_matches_the_real_response_shape():
    data = voice.mock_tts("Hello there. Bye.")
    assert base64.b64decode(data["audio_base64"])
    assert [w["w"] for w in voice.words_from_alignment(data["alignment"])] == ["Hello", "there.", "Bye."]


def test_saved_voice_is_reused_only_for_the_same_script(tmp_path, monkeypatch):
    calls = []

    def fake(text):
        calls.append(text)
        return {"audio_base64": "", "alignment": {}}

    monkeypatch.setattr(voice, "mock_tts", fake)
    voice.get_raw_voice(str(tmp_path), "first", "mock")
    voice.get_raw_voice(str(tmp_path), "first", "mock")
    assert calls == ["first"]
    voice.get_raw_voice(str(tmp_path), "changed", "mock")
    assert calls == ["first", "changed"]


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"audio_base64": "", "alignment": {}}).encode()


def test_elevenlabs_request_uses_the_environment(monkeypatch):
    seen = {}

    def fake_open(request, timeout):
        seen["url"], seen["key"] = request.full_url, request.get_header("Xi-api-key")
        seen["body"] = json.loads(request.data)
        return FakeResponse()

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice")
    monkeypatch.setattr(voice.urllib.request, "urlopen", fake_open)
    voice.elevenlabs_tts("hello")
    assert "/test-voice/with-timestamps" in seen["url"]
    assert seen["key"] == "test-key"
    assert seen["body"]["text"] == "hello"


def test_elevenlabs_without_credentials_stops_cleanly(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    with pytest.raises(SystemExit):
        voice.elevenlabs_tts("hello")


def test_dotenv_does_not_override_the_environment(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\nDEMO_A="from-file"\nDEMO_B=from-file\n')
    monkeypatch.delenv("DEMO_A", raising=False)
    monkeypatch.setenv("DEMO_B", "from-env")
    voice.load_dotenv(str(env))
    assert voice.os.environ["DEMO_A"] == "from-file"
    assert voice.os.environ["DEMO_B"] == "from-env"
    monkeypatch.delenv("DEMO_A")
