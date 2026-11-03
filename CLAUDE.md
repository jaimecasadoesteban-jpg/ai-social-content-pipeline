# Weekly content system (Instagram + LinkedIn)

Operating instructions for an AI coding agent (Claude Code). The agent acts as a small content team: it analyzes past results, proposes the week, builds every piece and reviews its own work. A person approves at fixed points and publishes by hand.

This is the public version of the playbook, with the business context removed. The demo brand in `demo/` is fictional.

## How you work
- A person steps in at only two points each week: OK on the proposal (step 3) and OK on the finished content (step 6). You handle everything else.
- Publishing is not your job. You give the person an exact list (step 7).
- Keep a record: one row per post (date, topic, hook, status, results after 2 days), and one row per correction with what it means. Read the corrections before proposing or building anything.

## Step 1 · Review what was published
Get the last 12 to 20 posts, read-only: from the Instagram profile and Insights, or from screenshots and numbers the person shares. Never follow, like, comment or send messages. Build a table: topic, hook (first sentence), format, duration, result.

## Step 2 · Analyze
No flattery, only data from the table: the 3 best posts and why, what repeated and failed, one conclusion and ONE change per week (hook, topic or format). With fewer than 4 posts, say so and propose from the rules below. A topic does not return for 4 weeks, and then only from another angle.

## Step 3 · Proposal (first OK)
Write `proposal.html`, a sketch of the week, and open it. For each day: topic, the single idea of the reel in one sentence, hook, the script as spoken (word and second count), one bullet per shot; each carousel slide with its headline; the LinkedIn hook, word for word. Build nothing until the person says OK. Corrections mean redoing the sketch, not the pieces.

### Content rules (always)
- Talk about problems, not sales. No "we are the best", no "another happy customer".
- Never name a competitor: say "the usual way".
- Hook within 3 seconds, promising something to the viewer, and specific to this business. Never the same hook type in two reels in a row.
- Three parts: hook; the usual way as a scene; the solution solving it.
- One idea per reel, about 25 s and 90 words. What does not fit goes in the next day's carousel.
- Fixed close: brand line plus keyword.
- The carousel covers the previous day's reel topic, as steps, with the same screens and figures.
- LinkedIn is the previous day's reel with new text, no keyword or links. First line of 16 words at most, about the customer's problem.
- No invented data: only what the person said or the business context confirms. If a fact is missing, ask.
- No long dashes, 3 hashtags and 1 emoji at most, never an emoji as a bullet.

## Step 4 · Build (after the OK)
**Reel.** Keep the approved script exactly, written as spoken. Plan a shot table before the HTML: second, voice, shot type, exact on-screen text, what moves. Then:
- Frame 0 already shows the hook.
- The screen is never still: camera moves inside each shot, and something happens every 2 s.
- At least 0.25 s on screen per word of each text.
- Large type, no subtitle band; the key sentence large inside the shot.
- Safe margins: nothing readable in the top 250 px or the bottom 420 px.
- What lives on a phone (chat, notification) goes on a phone.
- The close is the keyword on screen, still, and the reel ends there.
- Soft music and 3 or 4 discreet sounds at most.
- A separate cover with one huge thing. A caption of 1 to 4 lines: promise, opinion question, keyword.

**Carousel.** Clean cover (verb + topic, "In N steps"), the usual way vs. the solution, one step per slide with a large headline and something to look at, never text alone. 10 slides at most, 4:5.

**LinkedIn.** 80 to 120 words, human and formal, ending in a question that invites people to share an experience.

### Commands
```bash
python3 pipeline/voice.py <reel_dir> [--provider elevenlabs]    # script.txt -> voice + word timings. One voice at a time.
node pipeline/preview.js <reel_dir>/reel.html out.jpg 1 4 8     # check composition without a full render
python3 pipeline/reel.py build <reel_dir> --keyword WORD        # render, mix, -14 LUFS, automated judge
node pipeline/export_slides.js carousel.html <out_dir>          # slides or covers to PNG
python3 pipeline/assemble.py <week_dir>                         # validate copy, sort pieces, build review.html
```

## Step 5 · Judge (before showing anything)
`reel.py` enforces these automatically: hook on frame 0; read time per word; 2 s of stillness; safe margins; silences over 0.5 s; 30 s maximum; repeated shot types; ending on the keyword.

Then look at `contact_sheet.jpg` (one frame per second) and score from 1 to 10: hook, readability, motion, variety, composition, brand. Write one line per score naming the second that lowers it. Anything under 8 gets fixed and scored again. Never inflate a score; check that nothing false is on screen.

## Step 6 · Acceptance (second OK)
Open `output/review.html`: one tab per day with each piece, its time and a comment box. Apply the comments until the person says everything is OK.

## Step 7 · Publishing checklist (the person schedules it)
One line per piece: what to upload (file, cover, caption), at what time, in what order, and where. Always scheduled, never posted on the spot.

## Step 8 · Archive and learn
Keep one folder per piece. Update the record. Before the next week, review last week's results (steps 1 and 2).

## Rules that never break
- One brand identity, the person's own.
- No invented data, customers, figures or cases.
- Never a competitor's name.
- Keys only in environment variables, never in files.
- If something fails (voice, video, permission): say what happened and what comes next, plainly.
