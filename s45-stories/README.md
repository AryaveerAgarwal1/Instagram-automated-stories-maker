# s45 Story Sequences

An Instagram Story sequence engine for s45, an AI-native investment banking startup
in India. Built to the spec in `.claude/skills/s45-story-sequences/SKILL.md`.

The loop:

> a week of topics &rarr; Claude writes configs &rarr; renderer draws frames &rarr; a named
> approver signs off &rarr; scheduler publishes only what was approved &rarr; everything
> is archived.

---

## Run it

Open this folder in VS Code, then in the integrated terminal:

```bash
pip install -r requirements.txt
python run.py
```

That starts the backend and opens the review app at **http://127.0.0.1:8045**.
Sample sequences ship with the project, so frames are on screen immediately. There is
no photo library to supply: every frame is drawn from `config/brand.json`.

Windows note: use `py -m pip install -r requirements.txt` and `py run.py` if
`python` is not on your PATH. There is nothing to build and no npm - the frontend is
plain HTML, CSS and JavaScript served by the same process.

VS Code users get three ready-made launch configs (F5): run the app, render
everything, validate the week.

---

## Read this before you post anything

**This project is not legal advice and does not substitute for Indian counsel.**
Two questions have to be answered by a lawyer before the first post, because they
determine roughly a third of `config/policy.json`:

1. **Is s45 a SEBI-regulated entity, and under what registration?** Goes into
   `entity_status`. It ships as `TBD_BY_COUNSEL` and the app warns loudly while it
   stays that way.
2. **Does the February 2026 social media disclosure circular apply to s45?**
   Effective 1 May 2026, it requires regulated entities to display their
   SEBI-registered name and registration number at the beginning of
   securities-market-related content, including in closed groups. If yes, the
   identity block on frame 1 is mandatory. If no, keep it anyway.

`config/policy.json` ships with **demo registration values**. Replace them with the
real registered name and number, exactly as registered. To watch the hard stop fire,
put the word `PLACEHOLDER` into either field and run `python render.py --all`.

---

## What is where

```
render.py                  the deterministic renderer + validator CLI
schedule.py                the publisher (refuses unapproved configs)
archive.py                 the immutable publication record
run.py                     starts the local review app

config/policy.json         registration, disclosures, banned terms, approval rules
config/brand.json          the whole visual system - teal field, grid, fonts, panels, charts

s45core/core.py            paths, config, ledgers, hashing
s45core/validate.py        every validation rule, each naming itself on failure
s45core/render_engine.py   the 15-point renderer spec

server/app.py              FastAPI wrapper over exactly the same code
web/                       the review app (no build step)

assets/artifacts/          redacted memo pages, model structures. Nothing client-identifying
assets/fonts/              serif for headlines, mono for labels, sans for body
ledgers/asks.json          active and retired asks
sequences/<slug>/          config.json, frames, post-order.md, approval.json
archive/<date>/<slug>/     frames + config + approval + assets, SHA-256 manifest

tools/seed_assets.py       generates the placeholder artifact pages
tools/acceptance.py        every acceptance check from the skill file
prompts/generate-week.md   the weekly batch prompt for Claude
```

---

## The look

Every frame is drawn. There is no photography and no image library.

The field is deep teal with a graph-paper grid, a corner vignette, the S45 lockup and a
hairline footer rule. `background.type` picks how much chrome shows: `note` adds the
`S45 | CAPITAL MARKETS NOTE` kicker and belongs on frame 1 and on any frame carrying
metrics; `field` leaves it off.

On top of that, a frame may carry any of five drawn panels, in this order:

| Panel | Shape | Cap |
|---|---|---|
| `eyebrow` | a mono dateline above the headline | ~48 chars |
| `metrics` | `[{label, value, delta, direction}]` | 3 cards |
| `chart` | `{type, title, unit, labels, series, source}` | 12 points, 4 series |
| `bullets` | `["...", ...]` under a WHAT CHANGED label | 8 rows |
| `signal` | one sentence in the bordered callout | ~190 chars |

Three things about charts are worth stating plainly, because they are the reason this
is not just a plotting library:

1. **The values live in `config.json`.** Nothing is fetched at render time. A frame
   that phoned out for data could not be re-rendered identically in three years, and
   reproducibility is what the retention obligation actually rests on.
2. **`direction` on a metric is required, not inferred.** Green on a fall is a factual
   error rendered in the house style, and a regex looking at `-0.0% WoW` cannot tell
   you which way the week went.
3. **A chart is held to the written standard.** It needs a source, its values must line
   up with its labels, and approval covers it exactly as it covers the sentence beside
   it.

What this trades away: the asset cooldown, the photo library and the 40-photograph
prerequisite are all gone, because there is no longer a file that can be reused,
misplaced or quietly swapped after approval. What it costs: every frame now comes from
the same well, so sameness is the live risk rather than repetition. `--check-week`
watches for it - duplicate headlines are an error, and a week where every sequence
leans on a chart is a warning.

---

## The CLI

```bash
python render.py sequences/<slug>              # render all frames
python render.py sequences/<slug> --frame 4    # re-render frame 4 + its continuations
python render.py sequences/<slug> --validate   # check without rendering
python render.py --check-week sequences/       # cross-validate the batch
python render.py --all                         # render everything

python schedule.py sequences/<slug> --dry-run  # run every gate, push nothing
python schedule.py sequences/<slug> --mark-hand-posted
python archive.py  sequences/<slug>

python tools/acceptance.py                     # 42 checks, run on a temp copy
```

The review app calls the same functions. Nothing the UI does can bypass a rule the
CLI enforces.

---

## The five refusals that matter

Each one names its rule and quotes the offending span.

| Rule | What it stops |
|---|---|
| `identity_block_hard_stop` | Rendering at all while the registration fields are empty. The identity block never degrades. |
| `scope_attestation` | A config that has not stated `private_markets_only`. Missing is a hard failure, not a default. |
| `listed_security_scan` | Any block, source line or ask string matching the banned terms and patterns. |
| `artifact_path` | Compositing anything outside `assets/artifacts/`. This is the structural block on a client screenshot reaching a frame. |
| `background_photo_retired` | A config still asking for a photo background. The refusal names the replacement rather than silently degrading to `field`. |
| `statistic_requires_source` | A chart or metric row with no source anywhere. A plotted number is held to the written one's standard. |
| `chart_series_length` | A series whose values do not line up with its labels. A chart whose points miss its axis misstates the data. |
| `metric_direction` | A delta with no stated direction. The renderer colours from that field and will not guess it from a minus sign. |
| `statistic_requires_source` | A digit-bearing statistic with no `source_line`. A number without a source does not render. |

Plus, in `schedule.py`: no `approval.json`, an approver outside `policy.approvers`,
an agent-written approval, a frame changed after sign-off, a hand-post-only frame,
or a second push of something already published.

---

## The approval gate

A rendered sequence is **not publishable** until `sequences/<slug>/approval.json`
exists, carrying an approver from `policy.approvers`, a timestamp, and the SHA-256
of every frame PNG. `schedule.py` recomputes those hashes before pushing: change one
pixel after sign-off and the approval is void.

Claude never writes `approval.json`. The Approve button in the review app writes it
with the approver's identity, and the tooling treats an agent-written approval as
invalid.

Two sample sequences ship pre-approved so the Pipeline view shows every state. Revoke
one in the app to watch `schedule.py` refuse it.

---

## Publishing

- **Hand-post** every `cta` sequence and anything carrying a poll. Auto-published
  stories have no native stickers, no tappable links, no music.
- **Schedule** the rest. All frames go out as **one story post carrying the images in
  order**, never N separate posts - separate posts publish out of order and a
  scrambled argument is worse than none.
- Save each sequence to a Highlight. A founder landing on the profile in month four
  should be able to read six months of thinking on demand.
- Run `archive.py` immediately after publishing.
- The identity block also belongs on the Instagram bio and at the top of any WhatsApp
  broadcast. The circular reaches closed groups.

`push_story()` in `schedule.py` is the one integration point, deliberately
unimplemented. Wire it to whichever Graph API or scheduling tool s45 uses. Every gate
above it is the part that must not be bypassed.

---

## Before daily cadence

1. Counsel answers Q1 and Q2. Fill in `policy.json`.
2. Replace `assets/artifacts/` with genuinely redacted pages. The placeholders are
   labelled as placeholders on purpose.
3. Feed Claude 3-5 samples of the principals' actual writing before generating.
4. Write thirty topics. At one sequence a day the binding constraint is topic supply
   and, for anything charted, verified numbers - not the code.
5. Update the Instagram bio with the registered name and number. Count the characters.

Then per week: run `prompts/generate-week.md`, review, approve sequence by sequence,
schedule the non-asks, hand-post the ask, archive.

**The one rule that makes it work:** be right in public, be identifiable, and be able
to prove what you published.
