import numpy as np

import reel


def item(k=0, txt="Hello world", x=100, y=400, w=500, h=80, o=1.0):
    return dict(k=k, txt=txt, x=x, y=y, w=w, h=h, o=o)


def frames(items_by_time):
    return [{"t": t, "items": items} for t, items in items_by_time]


def test_text_inside_safe_area_passes():
    assert reel.check_margins(frames([(0, [item()])])) == []


def test_text_under_the_instagram_interface_fails():
    assert reel.check_margins(frames([(0, [item(y=1450, h=100)])]))
    assert reel.check_margins(frames([(0, [item(y=100)])]))


def test_faded_text_does_not_count_for_margins():
    assert reel.check_margins(frames([(0, [item(y=100, o=0.3)])])) == []


def timeline(seconds, text, fps=30):
    """Text visible for `seconds`, then 2 s without it."""
    out = [(i / fps, [item(txt=text)]) for i in range(int(seconds * fps))]
    out += [(seconds + i / fps, []) for i in range(2 * fps)]
    return frames(out)


def test_text_shown_too_briefly_fails():
    assert reel.check_read_time(timeline(0.5, "one two three four"))


def test_text_shown_long_enough_passes():
    assert reel.check_read_time(timeline(1.1, "one two three four")) == []


def test_text_on_the_final_frame_is_exempt():
    assert reel.check_read_time(frames([(0, []), (1, [item(txt="one two three four")])])) == []


def test_keyword_must_be_on_the_last_frame():
    assert reel.check_keyword(frames([(0, [item(txt="DEMO")])]), "DEMO") == []
    assert reel.check_keyword(frames([(0, [item(txt="DEMO")]), (1, [item(txt="Bye")])]), "DEMO")


def test_frame_zero_needs_the_hook():
    assert reel.check_first_frame(frames([(0, [item(txt="Big hook")])])) == []
    assert reel.check_first_frame(frames([(0, [])]))


def test_same_shot_type_twice_fails():
    a, b = dict(type="Phone", start=0), dict(type="Phone", start=3)
    assert reel.check_shot_variety([a, b])
    assert reel.check_shot_variety([a, dict(type="Chart", start=3)]) == []


def test_still_screen_fails_and_motion_passes():
    still = np.zeros((100, 4, 4), np.float32)
    assert reel.check_stillness(still)
    moving = still.copy()
    moving[::20] = 50
    assert reel.check_stillness(moving) == []
