---
name: s45-story-sequences
description: Build an automated Instagram Story sequence engine for s45, an AI-native investment banking startup in India. Three content types scoped to private markets, a proof standard that never touches client material, a mandatory SEBI identity block on the opening frame, an approval gate the scheduler cannot bypass, an asset cooldown ledger for daily cadence, and a deterministic renderer that turns a week of topics into ready-to-post 1080x1920 frames. Use when the firm needs a consistent, credible, compliant story presence without a human designing frames every morning.
---

# s45 Story Sequences (India)

s45 is an AI-native investment banking startup operating in India. Instagram is not an origination channel for that business and this system does not pretend otherwise. Mandates come from warm intros, promoter and founder networks, PE/VC relationships, and inbound to a named person. What Instagram does is make s45 legible to the people deciding whether to take that intro: founders sizing up who understands their category, operators considering joining, co-advisors and funds forming an impression before the first call.

The objective is **credibility and talent**, not lead capture. The engine is standard story automation — one config per sequence, a deterministic renderer, a shared asset library — but the content scope, the proof standard, the mandatory disclosure, and what is allowed to publish without a human are all shaped by the Indian regime.

The loop:

> a week of topics -> Claude writes configs -> renderer draws frames -> a named approver signs off -> scheduler publishes only what was approved -> everything is archived.

---

## Amendment: the visual system moved off photography

This file was written for a system whose frames sat on photographs from a shared,
cooldown-governed library. **That is no longer how it works.** Where the sections below
say "photo", "background library" or "asset cooldown", read this instead:

- **Every frame is drawn** from `config/brand.json` — deep teal field, graph-paper grid,
  the S45 lockup, a hairline footer rule. `background.type` is `field` (quiet) or `note`
  (adds the `S45 | CAPITAL MARKETS NOTE` kicker). There is no `assets/backgrounds/`
  folder and nothing to upload.
- **The asset cooldown is retired**, along with `ledgers/asset-usage.json` as a render-time
  input. It existed to stop a small photo library repeating itself; a drawn field cannot
  repeat itself into a file collision. The batch-level risk moved from *reuse* to
  *sameness*, and `--check-week` now watches that instead: duplicate opening headlines are
  an error, and a week where every sequence leans on a chart is a warning.
- **Frames carry drawn panels**: `eyebrow`, `metrics` (max 3 cards), `chart` (bar or line),
  `bullets` (max 8, under a WHAT CHANGED label), `signal` (one sentence in a callout).
  A frame carrying a panel cannot be followed by a `continues` frame.
- **Charts are rendered from values in the config**, never from a live feed, for the same
  reason everything else here is deterministic: a frame that fetched data at render time
  could not be re-rendered identically once the retention clock matters. A chart needs a
  source, its values must line up with its labels, and `direction` on a metric delta is
  required rather than inferred — green on a fall is a factual error rendered in the
  house style.

The compliance spine is unchanged: the identity block hard stop, the scope attestation,
the listed-security scan, the artifact path restriction, statistic-requires-source and
the approval gate all work exactly as described below, and `statistic_requires_source`
now covers plotted numbers as well as written ones.

---

## Read this before you build anything

**This file is not legal advice and does not substitute for Indian counsel.** Two questions must be answered by a lawyer before the first post, because they determine roughly a third of the configuration below:

**Q1. Is s45 a SEBI-regulated entity, and under what registration?** Managing public issues in India requires SEBI merchant banker registration. Publishing research or giving advice on securities pulls toward Research Analyst or Investment Adviser registration. Private M&A and private placement advisory for unlisted companies sits differently again. The answer goes into `policy.json` as `entity_status` and drives everything downstream.

**Q2. Does the February 2026 social media disclosure circular apply to s45?** SEBI's circular, effective **1 May 2026**, requires regulated entities and their agents to display their SEBI-registered name and registration number on their social media handle home pages and **at the beginning of securities-market-related content**. It applies to intermediaries registered under Section 12 of the SEBI Act, 1992 and to persons regulated by SEBI, and it covers content on any platform including closed groups. It applies only to content posted on or after 1 May 2026; earlier posts need not be revisited.

If Q2 is yes, the identity block in Part 1 is mandatory and non-negotiable on frame 1 of every sequence. If Q2 is no, keep the block anyway — a firm asking founders to trust it with a mandate gains nothing by being harder to identify than its regulated competitors.

Also relevant regardless of registration status: SEBI's finfluencer regime. Regulated entities are barred from using unregistered financial influencers for marketing, advertising or performance claims — which removes creator collaborations as a growth lever if s45 is registered. And unregistered parties commenting on markets face a narrowed space: no live stock prices, historical data only with a lag, and a sharp line between neutral education and actionable advice. The December 2025 order against Avadhut Sathe — market ban plus impounding of over ₹546 crore — turned on education framing used to cover unregistered advisory. Verify the current state of all of this with counsel; the regime has moved every few months.

**The content consequence, which shapes Part 1:** s45 talks about **private markets only.** No commentary on listed securities, indices, prints, or anything with a live price. That is not a stylistic preference; it is the boundary that keeps a promotional story frame from being read as a recommendation.

Assumed posture: **founder-led challenger.** s45 has named principals who can be photographed and a thesis worth arguing. Part 5 has the dial-down if s45 later wants to read as an established institution. Do not try to be both accounts at once.

---

## How to use this

1. **As a Claude Code skill (recommended).** Save as `.claude/skills/s45-story-sequences/SKILL.md` in a project folder, then: "use the s45-story-sequences skill and build the system."
2. **Framework only.** Use Part 1 as a manual playbook. Slower, but the content and compliance rules are the half that matters.

---

## Part 1 - The framework

### The three content types

Every sequence is exactly one of these. Note what is absent: there is no market-read type. Listed-market commentary is out of scope for s45.

| Type | Job | Ends in an ask? |
|---|---|---|
| `private_markets` | A read on private-market activity: what founders are being offered on terms, how a category is being valued, where diligence practice is behind. Unlisted companies only. | No |
| `thesis` | How s45 thinks about a problem — diligence on AI-native revenue, why a category is mispriced, what a real data moat looks like. The core credibility type. | No |
| `build` | Building the bank in public: what was shipped, what was learned, what was wrong last quarter. The human register. | No |
| `cta` | Any of the above, ending in one concrete next step: a research signup, the careers page, a named partner's email. | Yes |

Rhythm: **4 non-ask sequences for every 1 ask.** An advisory firm that asks constantly reads as a brokerage pitch, which is precisely the register the Indian regulator has spent two years policing.

### The structures

5 to 7 frames. One beat, one job. Frame 1 always carries the identity block (see below) in addition to its hook.

**`private_markets`**

| Frame | Role | What it does |
|---|---|---|
| 1 | hook | The pattern, stated plainly. No teasing. Identity block. |
| 2-3 | read | What most people conclude, and where that is incomplete |
| 4-5 | mechanism | Why it happens — one layer below the headline |
| 6 | implication | What it means for a founder or an acquirer deciding this quarter |
| 7 | optional | An open question. Poll sticker if hand-posted. |

**`thesis`**

| Frame | Role | What it does |
|---|---|---|
| 1 | hook | The claim, sharp enough to disagree with. Identity block. |
| 2-3 | argument | The reasoning, in steps a non-specialist can follow |
| 4-5 | evidence | Public, citable, cleared. See the proof standard. |
| 6 | counter | The strongest objection, stated fairly, then answered |
| 7 | optional | Where s45 lands, in one line |

The `counter` frame is not decoration. Naming the best argument against your own position is the cheapest credibility signal available to a new firm, and it is the frame every competitor skips.

**`build`**

| Frame | Role | What it does |
|---|---|---|
| 1 | hook | The specific thing being built, or that broke. Identity block. |
| 2-3 | context | Why it matters to how s45 works |
| 4-5 | detail | The actual work: the screen, the model, the memo structure, the whiteboard |
| 6 | learned | What changed as a result, including what was wrong |
| 7 | optional | Human beat: the desk at 11pm, the team, the process |

**`cta`** — frames 1-5 follow whichever type fits, then:

| Frame | Role | What it does |
|---|---|---|
| 6 | bridge | Name the reader's situation. No urgency, no scarcity. |
| 7 | cta | The ask formula below, plus the disclosure line and a link sticker. Hand-posted. |

### The identity block

The single most India-specific element of this system.

- **Content:** s45's SEBI-registered name and registration number, exactly as registered, from `policy.json`. Never abbreviated, never stylised, never a logo substitute.
- **Placement:** frame 1 of every sequence, at a fixed position, at a fixed size and contrast set once in `brand.json` and **not overridable per sequence.** The point of fixing it is that it cannot be quietly shrunk on a frame someone wants to look cleaner.
- **Also on the profile.** Registered name and number on the Instagram bio. Budget the characters early — the bio limit gets tight fast, and it gets tighter if s45 ends up holding more than one registration.
- **Also on WhatsApp.** The circular reaches closed groups. If s45 broadcasts memos or research to a WhatsApp list, that list is a disclosure surface, not a private workaround. Same block at the top of the broadcast.
- If counsel concludes the circular does not bind s45, keep the block and drop the registration number, leaving the registered legal name. Identifiability is worth it on its own merits.

### Hook patterns

- **Plain pattern.** "Four AI infra rounds we saw this quarter priced off ARR alone. None of the four had a margin story."
- **Named misconception.** "Most diligence here still books inference cost as COGS. For two years it behaves more like R&D."
- **Category question.** "What is an AI company's revenue worth if the model underneath it commoditises in eighteen months?"
- **Correction of ourselves.** "We were wrong about this last quarter. Here is what changed."
- **Concrete artifact.** "This is the one page we ask every founder to fill in before we take a mandate."

Banned as hooks, without exception: any number attached to a deal, a client, or a return. Any "we closed", "we delivered", "our clients see". Any listed company, ticker, index, or live price. Any scarcity or urgency framing. Any selfie without an idea attached.

### The ask formula

Two permitted shapes, both non-keyword. Keyword replies route into Instagram DMs, which is the wrong channel for this buyer and creates an unarchived communication trail — a bad combination under an Indian retention regime.

> "If you [specific situation], [named resource] is at the link. No signup wall." — research, memos, frameworks.

> "If you [specific situation], email [name] at [address]. It goes to a person." — careers, coverage, co-advisory.

Rules:

- Specific situation, named artifact, named human. Never "DM us", never "reach out", never a keyword.
- No claim about outcomes. The link points to a document, not to a result.
- Every ask frame carries the disclosure line from `policy.json`, baked into the pixels so it survives scheduling.
- Ask frames are **hand-posted only** — they need a native link sticker, and they are the frames most likely to need a second read.

### The proof standard

The part that differs most from generic story frameworks, and the part that is not negotiable.

**Never usable as proof:**

- Screenshots of client messages, emails, or WhatsApp threads — even blurred, even with names removed, even with permission. Deal-side communications sit under NDA and may carry unpublished price-sensitive information about a listed counterparty. A scrubbed screenshot is still an exposure; a live-deal one is worse.
- Deal outcomes, multiples, valuations, or fees, whether named or attributed to "a client".
- Testimonials or endorsements of any kind, unless counsel has confirmed the applicable rule permits them and specified the disclosures.
- Pipeline, mandate counts, or anything implying a track record the firm cannot substantiate on demand.
- Internal dashboards containing client, deal, or counterparty names.
- Anything about a listed company that is not already public, and anything about a listed company at all in a promotional frame.

**Usable as proof:**

- Published s45 research, memos, and public writing. Cite the piece.
- Public filings and public private-market data, with the source visible on the frame.
- Named team credentials: prior institutions, coverage, tenure. Factual and verifiable.
- Cleared firm announcements: launches, hires, product releases, once approved.
- The work itself: a redacted memo template, a model structure, a diligence checklist, a whiteboard. The artifact, with nothing identifying on it.
- Aggregate, non-attributable statistics where counsel has cleared the specific wording.

The rule of thumb: **evidence, not receipts.** A new bank earns credibility by being visibly right in public, not by showing that someone paid it.

### The design rules

- **Two background modes.** `photo` — a real photograph of the principals and the firm's world, graded, under a gradient that darkens only where text sits. `field` — a restrained typographic frame: near-black, fine grain, one hairline rule, the s45 mark small in a corner. `field` is for data beats where a photo would be decorative. Never a bright solid, never a generated graphic, never stock.
- **Photo frames must contain something real:** a principal, the desk, the screen, the room, the whiteboard. No honest photo for a beat means `field`.
- **Text sits high**, background breathing below.
- **2-3 short lines per frame.** Headline plus one or two support lines. Reads in under three seconds.
- **One highlight per frame, maximum,** in one accent colour used forever, as a single hairline underline under the phrase that carries the frame. Most frames have none. The restraint is the institutional signal.
- **Photo pairs.** Each background carries a setup beat and a payoff beat; on the payoff the setup text stays in place, dimmed, and the new line lands bright below. Never more than three beats on one background.
- **Data beats show their source.** Any number carries a small source line beneath it. A number without a source does not render.
- **Identity block** on frame 1, fixed. **Disclosure line** on every `cta` frame and any frame carrying a statistic. Small, low, always legible — never at a size or contrast that reads as hidden.

### The voice rules

Feed Claude 3-5 samples of the principals' actual writing — a memo intro, a LinkedIn post, a transcribed voice note.

- Short, complete sentences. One idea each. A smart person talking, not a brochure.
- Specific and sourced beats vague and confident.
- Sentence case. No hashtags, no emojis, no em dashes.
- English by default. If a sequence runs in Hindi or another language, the identity block and disclosure line stay in English exactly as registered, and the whole sequence needs its own approval — do not machine-translate an approved sequence and publish it as the same one.
- First person plural for firm positions. First person singular only on `build` sequences from a named principal.
- Banned style: unlock, elevate, game-changer, seamless, supercharge, leverage as a verb, "dive in", "in today's landscape", "we're excited to announce".
- Banned outright, whatever the phrasing: guarantees, assured or projected returns, forward-looking claims about any security or market, anything readable as investment advice or a recommendation to transact, any reference to a listed company, ticker, index, or price.

---

## Part 2 - The build

One config per sequence, one deterministic Python renderer, a shared asset library, a policy file, two ledgers, and an archive. No AI at render time: same config in, same pixels out. An edit is a two-second round trip, and every published frame is reproducible from its config months later — which is exactly what a retention obligation needs.

### Folder layout

```
s45-stories/
  render.py                  # the renderer
  schedule.py                # the publisher (refuses unapproved configs)
  archive.py                 # writes the immutable publication record
  config/
    policy.json              # registration, disclosures, banned terms, approval rules
    brand.json               # the whole visual system: teal field, grid, fonts, panels, charts
  prompts/
    generate-week.md         # batch generation prompt
  assets/
    artifacts/    INDEX.md   # redacted memo pages, model shots, whiteboards
    fonts/                   # serif headlines, mono labels, sans body
  ledgers/
    asks.json                # active/retired asks and destinations
  sequences/
    <slug>/
      config.json
      sources/
      frame_1.png ... frame_N.png
      post-order.md
      approval.json          # written by the approver, never by Claude
  archive/
    <yyyy-mm-dd>/<slug>/     # frames + config + approval, hashed, write-once
```

### `config/policy.json`

The single place regulatory decisions live, so they bind every sequence without being restated:

```json
{
  "jurisdiction": "IN",
  "entity_status": "TBD_BY_COUNSEL",
  "sebi_registered_name": "TBD",
  "sebi_registration_numbers": [],
  "identity_block_required": true,
  "identity_block_scope": "frame_1_all_sequences",
  "requires_pre_approval": true,
  "approvers": ["name@s45.example"],
  "retention_days": 3650,
  "disclosure_lines": {
    "statistic": "Source shown. Not investment advice.",
    "cta": "Not investment advice. No offer or solicitation to transact in securities."
  },
  "banned_terms": [
    "guaranteed", "assured returns", "risk-free", "we closed", "our returns",
    "multibagger", "target price", "buy call", "sell call", "tip"
  ],
  "banned_patterns": [
    "\\b\\d+(\\.\\d+)?x\\s+(return|multiple)\\b",
    "\\b(NSE|BSE|NIFTY|SENSEX)\\b",
    "\\b[A-Z]{2,}\\s*:\\s*[A-Z]{2,}\\b"
  ],
  "listed_security_commentary_allowed": false,
  "client_proof_allowed": false,
  "testimonials_allowed": false,
  "keyword_ctas_allowed": false,
  "creator_collaborations_allowed": false
}
```

Every value here should trace to something counsel said. `entity_status` stays `TBD_BY_COUNSEL` until it doesn't, and `--validate` should warn loudly while it does.

### The config schema

```json
{
  "slug": "kebab-case-from-the-topic",
  "type": "thesis",
  "ask": null,
  "scope_attestation": "private_markets_only",
  "highlight_title": "How we think",
  "profile": { "handle": "@s45" },
  "frames": [
    {
      "n": 1,
      "role": "hook",
      "blocks": [
        { "text": "The headline claim, sharp enough to disagree with." },
        { "text": "The line that adds the specific.", "size": "med",
          "highlights": [ { "text": "the specific", "style": "underline" } ] }
      ],
      "background": { "type": "photo", "src": "desk-late-model-review.jpg", "zoom": 1.0, "focus": "center" },
      "artifact": null,
      "artifact_pos": null,
      "source_line": null,
      "text_position": "top",
      "sticker": null
    },
    {
      "n": 2,
      "role": "argument",
      "continues": true,
      "blocks": [ { "text": "The turn, landing bright below the dimmed setup." } ],
      "source_line": null,
      "sticker": null
    }
  ]
}
```

Note there is no identity block field. It is rendered from `policy.json` onto frame 1 automatically and cannot be switched off from a config. That is deliberate.

Validation rules — `--validate` must refuse to render anything that breaks these:

- `type` in {`private_markets`, `thesis`, `build`, `cta`}. `ask` is `null` unless `type` is `cta`, in which case it is `{"shape": "link"|"email", "destination": "...", "situation": "..."}` matching an active entry in `ledgers/asks.json`. Any keyword-shaped ask is refused while `keyword_ctas_allowed` is false.
- `scope_attestation` must be present and equal `private_markets_only`. A missing attestation is a hard failure. It exists so the generation step has to state the boundary rather than assume it.
- **Listed-security scan.** Every block, source line and ask string is checked against `banned_terms` and `banned_patterns`. A hit is a hard failure quoting the offending span. Maintain the pattern list as counsel advises; treat it as a floor, not a guarantee.
- 5-7 frames, `n` sequential from 1.
- 1-3 `blocks` per frame; first is the headline, rest are support. Optional `size` in {big, med, small}.
- At most one highlight per frame. `style` in {underline, text, strike}. Highlight text must be an exact 1-4 word substring of its own block.
- `background.type` in {`photo`, `field`}, required on every non-continuation frame. `photo` requires a `src` that resolves.
- **Cooldown check:** *superseded.* There is no `src` to reuse. What makes daily cadence survivable now is the batch check on sameness - duplicate headlines and chart monotony - not a per-file cooldown.
- `artifact` is `null` or a filename **from `assets/artifacts/` only** — no path outside that folder may be composited. This is the structural block on a client screenshot ever reaching a frame.
- **Any block containing a digit-bearing statistic requires a non-null `source_line`** on that frame, and that frame renders the statistic disclosure.
- `continues: true` (never on frame 1) inherits the previous background and anchor; omit `background` and `text_position`.
- `sticker` is `null`, a poll, or a link. Stickers are checklist instructions, never pixels.
- A `cta` sequence must end on frame N with `role: "cta"` and carry the cta disclosure line.
- Refuse to render at all while `policy.identity_block_required` is true and `sebi_registered_name` or `sebi_registration_numbers` is unset.

### The renderer spec

`render.py`, Pillow only, deterministic.

1. **Canvas 1080x1920**, one PNG per frame, `frame_<n>.png`.
2. **Photo background, cover-fit.** Scale and crop to fill, honour `zoom` and `focus`, bake EXIF orientation. Convert HEIC to JPG before ingest; Pillow cannot read it.
3. **Field background.** Near-black base, fine monochrome grain, one hairline rule at a fixed offset, the s45 mark small in a fixed corner at low opacity. Deliberately plain — it should read as a document, not a poster.
4. **Grade photos** slightly darker, more contrast, a touch more saturation. Values from `brand.json`, per-frame overridable.
5. **Gradient only behind the text anchor,** not the whole frame. Full-frame darkening is the strongest "this is an ad" tell.
6. **Identity block on frame 1.** Registered name and registration number from `policy.json`, at the fixed position, size and contrast in `brand.json`. Not configurable per sequence. Refuse to render frame 1 if the values are missing.
7. **Text stack** in the brand sans, white, anchored by `text_position`. Headline clearly larger than support lines. Lay out the text stack so it never collides with the identity block — reserve that band before wrapping, don't overprint and hope.
8. **Highlight** as one continuous rounded hairline in the accent colour just under the phrase, text above staying white. `text` colours the words; `strike` crosses them.
9. **Source line** small, directly beneath the block carrying the statistic, muted but legible.
10. **Disclosure line** at a fixed low position when policy requires it for that frame. Fixed size and contrast, not per-sequence configurable.
11. **Continuation frames** reuse the previous graded background, redraw the previous text stack at pixel-identical positions but dimmed with highlights dropped, then draw the new blocks bright below. Chains accumulate.
12. **Artifact card.** Composite from `assets/artifacts/` as a rounded card with a soft shadow at `artifact_pos`. Cap upscaling. Keep text clear of the card.
13. **Graceful degrade.** A missing artifact is skipped with a warning. Content that overruns the footer rule warns rather than shrinking the type - the renderer never rescues a frame by making it unreadable. **The identity block never degrades** — a missing registration is a hard stop, not a warning.
14. **Emit `post-order.md`:** frames in order, sticker instructions, which frames are hand-post-only, the Highlight title, the ask destination, a confirmation that frame 1 carries the identity block, and an explicit line stating the sequence is unapproved until `approval.json` exists.
15. **CLI:** `render.py sequences/<slug>` renders all; `--frame N` re-renders one plus its continuations; `--validate` checks without rendering; `--check-week sequences/` cross-validates a batch for duplicate headlines, duplicate asks and chart monotony.

### The asset library

**Superseded — see the amendment at the top.** There is no background library. The only
files left are artifacts, and they are files because a redacted memo page is a document
rather than a style.

- `assets/artifacts/` — redacted memo pages, model structures, checklist pages, framework sketches. **Redacted before they enter the folder; originals stored somewhere else entirely.** Nothing client-identifying ever lands here.
- It carries an `INDEX.md`, one line per file describing content and the beat it suits. Claude reads the INDEX at generation time and picks real files.
- The renderer composites artifact filenames from that folder and nowhere else. That restriction is the structural block on a client screenshot reaching a frame, and it survives the move off photography intact.

### The build prompt

```
Read the s45-story-sequences skill file. Build the system exactly to its Part 2 spec:

1. Create the folder layout, config/policy.json and config/brand.json (ask me for the
   accent colour, fonts, mark file, and the identity block position and size), and both
   ledgers initialised empty. Leave entity_status as TBD_BY_COUNSEL.
2. Write render.py with Pillow as the only dependency, implementing all 15 points of the
   renderer spec including --validate, --frame N, --check-week, and post-order.md.
3. Implement every validation rule. The ones that matter most: the identity block hard
   stop, the scope_attestation requirement, the listed-security term and pattern scan,
   the artifact path restriction, the 14-day asset cooldown, and statistic-requires-source.
   Each failure must name the rule and quote the offending span.
4. Write schedule.py so it refuses any sequence lacking a valid approval.json, refuses any
   sequence containing a hand-post-only frame, and records what it pushed.
5. Write archive.py to copy frames, config and approval into archive/<date>/<slug>/ with a
   SHA-256 manifest.
6. Create two sample sequences by hand — one thesis on photo backgrounds, one
   private_markets entirely on field backgrounds — so we can test the look without
   generating anything. Use placeholder registration values and show me the hard stop
   firing before I fill them in.
7. Render both and show me the frames.

Acceptance checks: every frame 1080x1920; frame 1 carries the identity block at the fixed
position and the text stack does not collide with it; text high with background breathing
below; one hairline accent underline, never two on a frame; continuation frames show
previous text dimmed in its exact position; field frames read as documents, not posters; a
statistic without a source_line is refused; a config mentioning NIFTY or a ticker is
refused with the span quoted; an artifact path outside assets/artifacts/ is refused; a
config reusing a photo from three days ago is refused; render refuses entirely while the
registration fields are empty; schedule.py refuses an unapproved sequence.
```

Tune the sample renders until the look is right. You are setting taste once.

---

## Part 3 - Making sequences

### The weekly batch prompt

Save as `prompts/generate-week.md`. At daily cadence you plan a week at a time.

```
Week of: <date>
Topics: <5 to 7 lines, one per sequence, with the type for each>
Cleared material: <published research, approved announcements, public data you want used.
  Anything not listed here is not available as evidence.>

You are writing a week of Instagram story sequences for s45, an AI-native investment
banking startup in India. Read the s45-story-sequences skill file first and follow it
exactly: the structure for each type, the hook patterns, the proof standard, the ask
formula, the design rules, the voice rules.

Hard constraints, non-negotiable:
- PRIVATE MARKETS ONLY. No listed company, ticker, index, price, or market print. Not as
  a topic, not as an aside, not as an analogy. Set scope_attestation on every config.
- The proof standard in Part 1. No client material of any kind. No deal outcomes, no
  testimonials, no numbers attached to a client. Evidence comes from the cleared material
  list or public sources you can name.
- Every statistic gets a source_line naming the source.
- At most one sequence this week is type cta.
- Nothing forward-looking about any security. Nothing that reads as advice or a
  recommendation to transact.

Then:
1. Read assets/artifacts/INDEX.md. There is no background library - every frame is
   drawn. Frame 1 takes {"type": "note"}, later frames {"type": "field"}.
2. Write sequences/<slug>/config.json for each topic, 5-7 frames each. Structure text
   sequences as pairs: a setup beat plus a continues payoff beat. Where a beat rests on
   numbers, use the drawn panels - eyebrow, metrics, chart, bullets, signal - rather than
   writing the figures into a sentence. Not every sequence gets a chart.
3. Run render.py --validate on each, then --check-week sequences/. Fix every error.
4. Render all of them.
5. Output a review sheet: for each sequence, the type, its evidence and where each piece
   came from, any line that could conceivably be read as advice, any frame you are unsure
   about, and any asset I still need to supply.

Do not create approval.json. Approval is mine.
```

That last line matters. The approval artifact must never be writable by the thing that generated the content.

### A worked example

A `thesis` sequence. Note what the evidence frame does and does not contain, and that frame 1 leaves room for the identity block.

```json
{
  "slug": "inference-cost-is-not-cogs",
  "type": "thesis",
  "ask": null,
  "scope_attestation": "private_markets_only",
  "highlight_title": "How we think",
  "profile": { "handle": "@s45" },
  "frames": [
    { "n": 1, "role": "hook",
      "blocks": [
        { "text": "Most diligence still books inference cost as cost of goods." },
        { "text": "For an AI-native company in its first two years, it behaves more like R&D.",
          "size": "med",
          "highlights": [ { "text": "more like R&D", "style": "underline" } ] } ],
      "background": { "type": "photo", "src": "desk-late-model-review.jpg", "zoom": 1.0, "focus": "center" },
      "artifact": null, "source_line": null, "text_position": "top", "sticker": null },

    { "n": 2, "role": "argument", "continues": true,
      "blocks": [
        { "text": "That one line item changes how the whole business gets valued." } ],
      "source_line": null, "sticker": null },

    { "n": 3, "role": "argument",
      "blocks": [
        { "text": "COGS is meant to scale with revenue and stay roughly flat per unit." },
        { "text": "Early inference spend does the opposite. It falls hard as the model and the routing improve.",
          "size": "med" } ],
      "background": { "type": "field" },
      "artifact": null, "source_line": null, "text_position": "top", "sticker": null },

    { "n": 4, "role": "argument", "continues": true,
      "blocks": [
        { "text": "So a gross margin taken at month six describes a company that no longer exists by month eighteen.",
          "highlights": [ { "text": "no longer exists", "style": "underline" } ] } ],
      "source_line": null, "sticker": null },

    { "n": 5, "role": "evidence",
      "blocks": [
        { "text": "Frontier model list pricing per million tokens has fallen by roughly an order of magnitude in two years." },
        { "text": "None of that was in the plan when those margins were first modelled.",
          "size": "med" } ],
      "background": { "type": "field" },
      "artifact": "diligence-margin-page-redacted.png", "artifact_pos": "lower",
      "source_line": "Published provider list pricing, 2024-2026. Not investment advice.",
      "text_position": "top", "sticker": null },

    { "n": 6, "role": "counter",
      "blocks": [
        { "text": "The fair objection: treat it as R&D and you can hide a business that never had a margin." },
        { "text": "True. Which is why we ask for unit economics at three model prices, not one.",
          "size": "med",
          "highlights": [ { "text": "three model prices", "style": "underline" } ] } ],
      "background": { "type": "photo", "src": "whiteboard-diligence-framework.jpg", "zoom": 1.0, "focus": "center" },
      "artifact": null, "source_line": null, "text_position": "top", "sticker": null },

    { "n": 7, "role": "optional", "continues": true,
      "blocks": [
        { "text": "Cheap to test now. Expensive to discover after the raise." } ],
      "source_line": null, "sticker": null }
  ]
}
```

Two photo pairs, two field frames, four highlights across seven frames, the one statistic sourced, the counter-argument stated fairly. No client, no deal, no outcome, no listed security, nothing s45 cannot substantiate on demand.

### Reviewing

Five minutes per sequence: swap a background that misses the beat, tighten a line, move an underline. Edit `config.json` and re-render the touched frame with `--frame N`. Then it sits until approved.

---

## Part 4 - Approval, publishing, archiving

### The approval gate

The structural difference between this and generic story automation, and why `schedule.py` is separate from `render.py`.

- A rendered sequence is **not publishable** until `sequences/<slug>/approval.json` exists, carrying an approver from `policy.approvers`, a timestamp, and the SHA-256 of every frame PNG.
- `schedule.py` recomputes those hashes before pushing. Any frame changed after approval invalidates the approval and the push is refused. Re-render, re-approve.
- Claude never writes `approval.json`. The generation prompt forbids it; the tooling should treat a Claude-written approval as invalid.
- Approval is per sequence, not per week. Approving a batch in one click defeats the purpose.
- If s45 is a regulated entity, the approver should be whoever counsel designates for marketing communications — not whoever is free that morning.

### Publishing

- **Hand-post** every `cta` sequence and any sequence carrying a poll. Auto-published stories have no native stickers, no tappable links, no music. Three minutes in the app buys the link sticker that makes the ask work at all.
- **Schedule** the `private_markets`, `thesis` and `build` sequences. Push all frames as **one story post carrying the images in order**, never N separate posts — separate posts publish out of order and a scrambled argument is worse than none.
- Keep a `schedule.json` record per sequence so the script refuses to double-post.
- Save each sequence to a Highlight using its `highlight_title`. This matters more than the 24-hour window: a founder landing on the profile in month four should be able to read six months of thinking on demand. Suggested: "How we think", "Private markets", "Building s45", "Join us".
- **Other surfaces carry the same obligations.** A WhatsApp broadcast of the same content needs the identity block at the top, including in closed groups. Do not treat WhatsApp as the informal channel.

### Archiving

Run `archive.py` immediately after publishing. It copies frames, config and approval into `archive/<date>/<slug>/` with a hash manifest, retained for `policy.retention_days`. Because the renderer is deterministic, the archived config plus archived assets reproduce the exact published pixels — a stronger record than storing images alone, and the thing you will want if anyone ever asks what s45 published on a given day.

---

## Part 5 - Cadence, growth, and the five-a-day question

**Five frames a day** is the sane reading of the target, and the system supports it: **one sequence per day, 5 to 7 frames.** Five to seven sequences a week, one of which is a `cta`.

Five *sequences* a day — 25 to 35 frames — is a bad idea anywhere and worse here. Completion collapses well before frame 25, so the later sequences are seen by nobody, and an advisory firm producing that volume reads as retail promotion, which is exactly the register the Indian regulator has been narrowing.

At one sequence a day the binding constraint is not the code and not Claude. It is **topic supply, and verified numbers for anything charted.** Six real reads a week is a genuine editorial commitment. Before building, write thirty topics. If that list comes hard, run three a week and let quality carry it — three excellent sequences beat seven thin ones, and the system does not care which cadence you pick.

**On growth, one hard constraint.** If s45 is SEBI-registered, paid creator collaborations are off the table: regulated entities are barred from associating with unregistered financial influencers for marketing, advertising or performance claims. That removes the fastest Indian growth lever. What remains is the thesis itself, which is fine — a contrarian, well-argued position on how AI-native companies should be valued travels on its own in a way that office-life content from an unknown firm never will. Verify the current rule with counsel before commissioning anything from anyone.

**If s45 later shifts to an institutional register:** drop `build`, drop lifestyle frames, default to `field` backgrounds, cut to two or three sequences a week, replace first person singular with firm voice, route every ask to research or careers only. Same engine, different `brand.json`, shorter type list.

---

## Going further

Both are additions around the same config and renderer, so nothing gets rebuilt:

- **A local review app.** FastAPI plus one static page: list sequences, preview frames, edit a line, move an underline, swap a background, re-render live — and an approve button that writes a properly hashed `approval.json` with the approver's identity. This is where the approval gate stops being friction.
- **A source-linked data card renderer.** A script that draws a clean chart from public private-market data with the source and retrieval date baked into the image. Real, citable, honestly labelled — the strongest evidence frame available to a firm that cannot show client work.

---

## Running it

1. Get counsel to answer Q1 and Q2 at the top of this file. Fill in `policy.json`. Do this first; the renderer will refuse to run until you do.
2. Build the system with the build prompt. Tune the sample renders until the look is right.
3. Fill the libraries: 40+ named photos, a set of redacted artifacts, INDEX lines for both.
4. Update the Instagram bio with the registered name and number. Count the characters.
5. Write thirty topics.
6. Per week: run the batch prompt, review, approve sequence by sequence, schedule the non-asks, hand-post the ask, archive.

## The one rule that makes it work

**Be right in public, be identifiable, and be able to prove what you published.** The credibility comes from the thinking, not the asking — and nothing in this pipeline publishes without a named human's approval attached to the exact pixels that went out.
