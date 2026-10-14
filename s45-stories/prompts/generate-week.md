# Weekly batch prompt

At daily cadence you plan a week at a time. Fill in the three fields at the top and
give the whole thing to Claude in this project folder.

---

```
Week of: <date>
Topics: <5 to 7 lines, one per sequence, with the type for each>
Cleared material: <published research, approved announcements, public data you want
  used. Anything not listed here is not available as evidence.>

You are writing a week of Instagram story sequences for s45, an AI-native investment
banking startup in India. Read the s45-story-sequences skill file first and follow it
exactly: the structure for each type, the hook patterns, the proof standard, the ask
formula, the design rules, the voice rules.

Hard constraints, non-negotiable:
- PRIVATE MARKETS ONLY. No listed company, ticker, index, price, or market print. Not
  as a topic, not as an aside, not as an analogy. Set scope_attestation on every config.
- The proof standard in Part 1. No client material of any kind. No deal outcomes, no
  testimonials, no numbers attached to a client. Evidence comes from the cleared
  material list or public sources you can name.
- Every statistic gets a source_line naming the source. That includes plotted ones:
  a chart or a metric row needs source_line, data_sources, or chart.source. A number
  you cannot source is a number you do not draw.
- At most one sequence this week is type cta.
- Nothing forward-looking about any security. Nothing that reads as advice or a
  recommendation to transact.

Then:
1. Read assets/artifacts/INDEX.md. There is no background library to pick from -
   every frame is drawn from config/brand.json. Frame 1 takes
   `{"type": "note"}` (the kicker chrome); later frames take `{"type": "field"}`.
2. Write sequences/<slug>/config.json for each topic, 5-7 frames each. Structure text
   sequences as pairs: a setup beat plus a `continues` payoff beat.
   Where a beat rests on numbers, use the drawn panels instead of writing the figures
   into a sentence:
   - `eyebrow`: a dateline above the headline, e.g. "Week ending 26 July 2026".
   - `metrics`: up to 3 cards, each {label, value, delta, direction}. `direction` is
     "up" | "down" | "flat" and is REQUIRED whenever there is a delta - it sets the
     colour, and the renderer will not infer it from a minus sign.
   - `chart`: {type: "bar"|"line", title, unit, labels: [...],
     series: [{name, values: [...], color_index}], source}. `values` are numbers, not
     strings, and there must be exactly one value per label. Max 12 points, max 4
     series; name every series once there is more than one.
   - `bullets`: up to 8 short lines under a "WHAT CHANGED:" label.
   - `signal`: one sentence, max ~190 characters, in the callout box.
   A frame carrying any of these panels cannot be followed by a `continues` frame -
   give the next beat its own background.
   Do not put a chart on every sequence. A chart is the strongest move available and
   it dulls with repetition; a week where the data frame is the exception reads as
   evidence, a week where it is the rule reads as a template.
3. Run `python render.py sequences/<slug> --validate` on each, then
   `python render.py --check-week sequences/`. Fix every error.
4. Render all of them.
5. Output a review sheet: for each sequence, the type, its evidence and where each
   piece came from, any line that could conceivably be read as advice, any frame you
   are unsure about, and any asset I still need to supply.

Do not create approval.json. Approval is mine.
```

---

That last line matters. The approval artifact must never be writable by the thing that
generated the content. `schedule.py` treats an agent-written approval as invalid, but
the prompt is the first line of defence.

## Before the first run

Feed Claude 3-5 samples of the principals' actual writing - a memo intro, a LinkedIn
post, a transcribed voice note. The voice rules in the skill file describe a register;
the samples are what make it sound like a specific person rather than a good imitation
of one.

## Reviewing

Five minutes per sequence. Tighten a line, move an underline, switch a frame between
`field` and `note`. Edit in the review app or in `config.json` directly, then re-render
the touched frame with `--frame N`. Then it sits until approved.

Charts get a sixth minute. Check every plotted value against the source named in
`chart.source` before approving - approval covers the chart exactly as it covers the
sentence beside it, and a mistyped value in a config is indistinguishable from a
deliberate claim once it is rendered into a PNG.
