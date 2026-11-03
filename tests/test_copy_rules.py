import json
import os

import assemble

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOOD_POST = "A short first line about the problem.\n\n" + "word " * 90 + "\n\nHave you seen this?"


def test_good_caption_passes():
    assert assemble.validate_caption("x", ["Promise.", "What do you think?", "Message us DEMO."], "DEMO") == []


def test_caption_rules():
    assert assemble.validate_caption("x", ["No keyword?"], "DEMO")
    assert assemble.validate_caption("x", ["DEMO, no question"], "DEMO")
    assert assemble.validate_caption("x", ["a", "b", "c", "d", "DEMO?"], "DEMO")
    assert assemble.validate_caption("x", ["DEMO? #a #b #c #d"], "DEMO")
    assert assemble.validate_caption("x", ["DEMO? — dash"], "DEMO")
    assert assemble.validate_caption("x", ["DEMO? \U0001F600\U0001F600"], "DEMO")


def test_good_linkedin_passes():
    assert assemble.validate_linkedin("x", GOOD_POST, "DEMO") == []


def test_linkedin_rules():
    assert assemble.validate_linkedin("x", "Too short?", "DEMO")
    assert assemble.validate_linkedin("x", GOOD_POST.replace("Have", "DEMO have"), "DEMO")
    assert assemble.validate_linkedin("x", GOOD_POST.replace("Have", "http://x.y have"), "DEMO")
    assert assemble.validate_linkedin("x", GOOD_POST.replace("this?", "this."), "DEMO")
    assert assemble.validate_linkedin("x", "long " * 17 + "\n" + GOOD_POST, "DEMO")


def test_low_score_blocks_the_week():
    assert assemble.validate_scores("x", {"hook": [7, "weak"]})
    assert assemble.validate_scores("x", {"hook": [8, "ok"]}) == []


def test_demo_content_passes_its_own_rules():
    with open(os.path.join(ROOT, "demo", "week", "content.json"), encoding="utf-8") as f:
        assert assemble.validate(json.load(f)) == []
