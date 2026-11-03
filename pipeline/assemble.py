"""Validate a week's copy, sort the finished pieces into folders and build the review page.

Usage:
    python3 pipeline/assemble.py demo/week

Reads <week>/content.json and what reel.py and export_slides.js generated.
Writes <week>/output/: one folder per piece (video, cover, caption, script with shot table)
and review.html, where a person approves or comments on everything before publishing.
"""
import html
import json
import os
import re
import shutil
import sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
MIN_SCORE = 8


def validate_common(name, text):
    errors = []
    if re.search("[—–]", text):
        errors.append(f"{name}: contains long dashes")
    if len(re.findall(r"#\w+", text)) > 3:
        errors.append(f"{name}: more than 3 hashtags")
    if len(EMOJI.findall(text)) > 1:
        errors.append(f"{name}: more than 1 emoji")
    return errors


def validate_caption(name, lines, keyword):
    text = "\n".join(lines)
    errors = validate_common(f"caption {name}", text)
    if not 1 <= len(lines) <= 4:
        errors.append(f"caption {name}: {len(lines)} lines (1 to 4 allowed)")
    if keyword not in text:
        errors.append(f"caption {name}: missing keyword {keyword}")
    if "?" not in text:
        errors.append(f"caption {name}: missing question")
    return errors


def validate_linkedin(name, text, keyword):
    errors = validate_common(f"linkedin {name}", text)
    words = len(text.split())
    first_line = text.split("\n")[0]
    if not 80 <= words <= 120:
        errors.append(f"linkedin {name}: {words} words (80 to 120 allowed)")
    if len(first_line.split()) > 16:
        errors.append(f"linkedin {name}: first line has {len(first_line.split())} words (16 max)")
    if keyword in text or "http" in text:
        errors.append(f"linkedin {name}: contains keyword or link")
    if not text.strip().endswith("?"):
        errors.append(f"linkedin {name}: does not end with a question")
    return errors


def validate_scores(name, scores):
    return [f"{name}: {key} scored {value[0]}, below {MIN_SCORE}" for key, value in scores.items() if value[0] < MIN_SCORE]


def validate(content):
    keyword = content["keyword"]
    errors = []
    for key, reel in content["reels"].items():
        errors += validate_caption(key, reel["caption"], keyword)
        errors += validate_scores(f"reel {key}", reel["scores"])
    for key, carousel in content["carousels"].items():
        errors += validate_caption(f"carousel_{key}", carousel["caption"], keyword)
    for key, post in content["linkedin"].items():
        errors += validate_linkedin(key, post["text"], keyword)
    return errors


def shot_table(folder):
    """Rebuild the shot table from what was really rendered, not from the plan."""
    with open(os.path.join(folder, "meta.json")) as f:
        meta = json.load(f)
    with open(os.path.join(folder, "audit.json")) as f:
        audit = json.load(f)
    words = []
    words_path = os.path.join(folder, "words.json")
    if os.path.exists(words_path):
        with open(words_path) as f:
            words = json.load(f)
    first_seen = {}
    for frame in audit:
        for item in frame["items"]:
            if item["o"] >= 0.6 and item["k"] not in first_seen:
                first_seen[item["k"]] = (frame["t"], item["txt"])
    rows = ["| Second | Voice | Shot type | On screen (exact text) |", "|---|---|---|---|"]
    for scene in meta["scenes"]:
        voice = " ".join(w["w"] for w in words if scene["start"] <= w["start"] < scene["end"]) or "(no voice)"
        texts, seen = [], set()
        for t, text in sorted(first_seen.values(), key=lambda v: v[0]):
            if scene["start"] - 0.01 <= t < scene["end"] and text not in seen:
                seen.add(text)
                texts.append(f'"{text}"')
        rows.append(f"| {scene['start']:.1f}-{scene['end']:.1f} | {voice} | {scene['type']} | {' / '.join(texts)} |")
    return "\n".join(rows)


def assemble_reel(week, output, key, reel):
    source = os.path.join(week, key)
    kind = "short-reel" if reel.get("short") else "reel"
    folder = os.path.join(output, f"{reel['folder']}-{kind}")
    os.makedirs(folder, exist_ok=True)
    shutil.copy(os.path.join(source, "reel.mp4"), os.path.join(folder, "reel.mp4"))
    shutil.copy(os.path.join(week, "covers", f"{key}.png"), os.path.join(folder, "cover.png"))
    with open(os.path.join(folder, "caption.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(reel["caption"]) + "\n")
    with open(os.path.join(source, "judge.json"), encoding="utf-8") as f:
        judge = json.load(f)
    script_path = os.path.join(source, "script.txt")
    script = "(No voice: on-screen text, music and sound effects only.)"
    if os.path.exists(script_path):
        with open(script_path, encoding="utf-8") as f:
            script = f.read().strip()
    scores = "\n".join(f"- **{name.capitalize()}: {value[0]}/10.** {value[1]}" for name, value in reel["scores"].items())
    with open(os.path.join(folder, "script.md"), "w", encoding="utf-8") as f:
        f.write(f"# {reel['topic']}\n\n**Hook type:** {reel['hook_type']} | **Duration:** {judge['duration']} s\n\n"
                f"## Script\n{script}\n\n## Shots\n{shot_table(source)}\n\n"
                f"## Review\nAutomated failures: {len(judge['failures'])}. Warnings: {len(judge['warnings'])}.\n{scores}\n")
    return dict(day=key, order=3, kind="Short reel" if reel.get("short") else "Reel", hour=reel["hour"], folder=folder,
                topic=reel["topic"], caption=reel["caption"], scores=reel["scores"], duration=judge["duration"])


def assemble_carousel(week, output, key, carousel):
    folder = os.path.join(output, f"{carousel['folder']}-carousel")
    os.makedirs(folder, exist_ok=True)
    source = os.path.join(week, key, "carousel")
    images = sorted(f for f in os.listdir(source) if f.endswith(".png"))
    for image in images:
        shutil.copy(os.path.join(source, image), os.path.join(folder, image))
    with open(os.path.join(folder, "caption.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(carousel["caption"]) + "\n")
    return dict(day=key, order=2, kind="Carousel", hour=carousel["hour"], folder=folder, topic=carousel["topic"],
                caption=carousel["caption"], images=images)


def assemble_linkedin(week, output, key, post):
    folder = os.path.join(output, f"{post['folder']}-linkedin")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "post.txt"), "w", encoding="utf-8") as f:
        f.write(post["text"] + "\n")
    shutil.copy(os.path.join(week, post["from_day"], "reel.mp4"), os.path.join(folder, "video.mp4"))
    return dict(day=key, order=1, kind="LinkedIn", hour=post["hour"], folder=folder, topic=post["topic"], text=post["text"],
                words=len(post["text"].split()))


def url(folder, name):
    return quote(os.path.basename(folder)) + "/" + quote(name)


def caption_html(lines):
    return '<div class="caption">' + "<br>".join(html.escape(line) for line in lines) + "</div>"


def piece_body(piece):
    kind, folder = piece["kind"], piece["folder"]
    if kind == "LinkedIn":
        body = (f'<div class="reel"><video controls playsinline preload="metadata" src="{url(folder, "video.mp4")}"></video>'
                f'<div><div class="post">{html.escape(piece["text"]).replace(chr(10), "<br>")}</div>'
                f'<div class="meta">{piece["words"]} words</div></div></div>')
        return body, piece["text"]
    if kind == "Carousel":
        slides = "".join(f'<img loading="lazy" src="{url(folder, name)}" alt="Slide {i + 1}">' for i, name in enumerate(piece["images"]))
        body = (f'<div class="slides">{slides}</div><div class="meta">{len(piece["images"])} slides, 4:5, {html.escape(piece["topic"])}</div>'
                + caption_html(piece["caption"]))
        return body, "\n".join(piece["caption"])
    scores = "".join(f"<li><b>{html.escape(n.capitalize())} {v[0]}</b>: {html.escape(v[1])}</li>" for n, v in piece["scores"].items())
    body = (f'<div class="reel"><video controls playsinline preload="metadata" poster="{url(folder, "cover.png")}" src="{url(folder, "reel.mp4")}"></video>'
            f'<div><div class="meta">{html.escape(piece["topic"])}, {piece["duration"]} s</div>{caption_html(piece["caption"])}'
            f'<div class="cover"><img src="{url(folder, "cover.png")}" alt="Cover"><span>Cover</span></div>'
            f'<ul class="scores">{scores}</ul><a class="link" href="{url(folder, "script.md")}">Script and shot table</a></div></div>')
    return body, "\n".join(piece["caption"])


def review_page(content, pieces, output):
    tabs, panels = [], []
    for day in content["days"]:
        key = day["key"]
        tabs.append(f'<button class="tab" data-t="{html.escape(key)}" role="tab">{html.escape(day["label"])}</button>')
        cards = []
        for piece in sorted((p for p in pieces if p["day"] == key), key=lambda p: p["order"]):
            kind = piece["kind"]
            piece_id = html.escape(f"{key}-{kind.lower().replace(' ', '-')}")
            body, copy_text = piece_body(piece)
            cards.append(f'<section class="card"><header><span class="tag t-{kind.split()[-1].lower()}">{kind}</span>'
                         f'<span class="hour">{html.escape(piece["hour"])}</span>'
                         f'<button class="copy" data-copy="{html.escape(copy_text, quote=True)}">Copy text</button></header>{body}'
                         f'<label class="comment">Your comments<textarea data-k="{piece_id}" placeholder="What would you change?"></textarea></label></section>')
        panels.append(f'<div class="panel" data-p="{html.escape(key)}" role="tabpanel">{"".join(cards)}</div>')
    font = os.path.relpath(os.path.join(ROOT, "assets", "fonts", "Montserrat.ttf"), output)
    page = (TEMPLATE.replace("{{TITLE}}", html.escape(content["week_label"])).replace("{{FONT}}", quote(font))
            .replace("{{TABS}}", "".join(tabs)).replace("{{PANELS}}", "".join(panels)).replace("{{FIRST}}", html.escape(content["days"][0]["key"])))
    with open(os.path.join(output, "review.html"), "w", encoding="utf-8") as f:
        f.write(page)


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<style>
@font-face{font-family:"Montserrat";src:url({{FONT}}) format("truetype");font-weight:100 900}
:root{--bg:#0A1320;--sf:#13202F;--sf2:#1A2B3D;--line:#27405A;--ink:#F5F5F7;--mut:#A3B4C6;--grad:linear-gradient(90deg,#10B981,#0EA5E9)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 "Montserrat",-apple-system,Helvetica,Arial,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:28px 16px 80px}
h1{margin:0 0 4px;font-size:28px;letter-spacing:-.5px}
.sub{color:var(--mut);margin:0 0 18px;font-size:15px}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:5;border-bottom:1px solid var(--line);margin-bottom:18px}
.tab{font:inherit;font-weight:700;font-size:14px;color:var(--ink);background:var(--sf);border:1px solid var(--line);border-radius:999px;padding:8px 16px;cursor:pointer}
.tab[aria-selected=true]{background:var(--grad);border-color:transparent}
.all{margin-left:auto;font:inherit;font-weight:700;font-size:14px;color:#fff;background:transparent;border:1px solid #14B8A6;border-radius:999px;padding:8px 16px;cursor:pointer}
.panel{display:none}.panel.on{display:block}
.card{background:var(--sf);border:1px solid var(--line);border-radius:18px;padding:18px 20px;margin-bottom:16px}
.card header{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.tag{font-size:12px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;border-radius:6px;padding:3px 9px;color:#fff}
.t-reel{background:#0F766E}.t-carousel{background:#6D5BD0}.t-linkedin{background:#0A66C2}
.hour{font-weight:800;font-size:18px}
.copy{margin-left:auto;font:inherit;font-size:13px;font-weight:700;color:var(--ink);background:var(--sf2);border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer}
.reel{display:grid;grid-template-columns:300px 1fr;gap:22px;align-items:start}
.reel video{width:300px;border-radius:14px;background:#000;aspect-ratio:9/16}
.meta{color:var(--mut);font-size:13px;margin:4px 0 10px}
.caption,.post{background:var(--sf2);border-radius:10px;padding:12px 14px;font-size:15px;margin-bottom:12px}
.cover{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--mut);margin-bottom:10px}
.cover img{width:70px;border-radius:8px}
.scores{margin:0 0 10px;padding-left:18px;font-size:13px;color:var(--mut)}.scores b{color:var(--ink)}
.link{color:#7DD3FC;font-size:13px}
.slides{display:flex;gap:10px;overflow-x:auto;padding-bottom:8px;scroll-snap-type:x mandatory}
.slides img{width:260px;flex:none;border-radius:10px;scroll-snap-align:start}
.comment{display:block;margin-top:12px;font-size:13px;font-weight:700;color:var(--mut)}
.comment textarea{display:block;width:100%;margin-top:6px;min-height:64px;font:inherit;font-size:14px;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:10px}
@media (max-width:700px){.reel{grid-template-columns:1fr}.reel video{width:100%}.all{margin-left:0}}
</style></head><body><div class="wrap">
<h1>{{TITLE}}</h1>
<p class="sub">Everything here passed the automated judge. Add comments on any piece, then copy them back to the agent. Nothing is published from this page.</p>
<div class="bar" role="tablist">{{TABS}}<button class="all" id="all">Copy comments</button></div>
{{PANELS}}
</div>
<script>
const tabs=[...document.querySelectorAll('.tab')], panels=[...document.querySelectorAll('.panel')];
function show(k){tabs.forEach(t=>t.setAttribute('aria-selected',t.dataset.t===k));panels.forEach(p=>p.classList.toggle('on',p.dataset.p===k));}
tabs.forEach(t=>t.onclick=()=>show(t.dataset.t));
show('{{FIRST}}');
document.querySelectorAll('textarea').forEach(a=>{try{a.value=localStorage.getItem('c:'+a.dataset.k)||''}catch(e){}
  a.oninput=()=>{try{localStorage.setItem('c:'+a.dataset.k,a.value)}catch(e){}}});
function copy(text,btn){const done=()=>{const o=btn.textContent;btn.textContent='Copied';setTimeout(()=>btn.textContent=o,1400)};
  const fallback=()=>{const t=document.createElement('textarea');t.value=text;document.body.appendChild(t);t.select();document.execCommand('copy');t.remove();done()};
  if(navigator.clipboard)navigator.clipboard.writeText(text).then(done,fallback);else fallback();}
document.querySelectorAll('.copy').forEach(b=>b.onclick=()=>copy(b.dataset.copy,b));
document.getElementById('all').onclick=e=>{const out=[];document.querySelectorAll('.card').forEach(c=>{const v=c.querySelector('textarea').value.trim();
  if(v){const p=c.closest('.panel').dataset.p;out.push(`${tabs.find(t=>t.dataset.t===p).textContent}, ${c.querySelector('.tag').textContent} ${c.querySelector('.hour').textContent}: ${v}`)}});
  copy(out.length?out.join('\\n'):'No comments',e.target)};
</script></body></html>
"""


def main(week):
    with open(os.path.join(week, "content.json"), encoding="utf-8") as f:
        content = json.load(f)
    errors = validate(content)
    if errors:
        print("COPY RULES FAILED:", *errors, sep="\n  ")
        sys.exit(1)
    output = os.path.join(week, "output")
    shutil.rmtree(output, ignore_errors=True)
    os.makedirs(output)
    pieces = [assemble_reel(week, output, k, v) for k, v in content["reels"].items()]
    pieces += [assemble_carousel(week, output, k, v) for k, v in content["carousels"].items()]
    pieces += [assemble_linkedin(week, output, k, v) for k, v in content["linkedin"].items()]
    review_page(content, pieces, output)
    print("Week assembled in", output)


if __name__ == "__main__":
    main(sys.argv[1])
