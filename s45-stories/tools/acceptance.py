#!/usr/bin/env python3
"""Every acceptance check from the skill file, run against the real code.

    python tools/acceptance.py
    python tools/acceptance.py --in-place    (run against this folder, not a copy)

Nothing here is mocked. Each check builds a real config or a real policy, calls the
real validator or the real renderer, and asserts the refusal fires with the right
rule named. Failures print the rule that should have caught it.

By default the whole project is copied to a temp folder first and the checks run
there, so a run can write approvals, stamp ledgers and break policy.json without
touching your working sequences.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def run_in_copy() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="s45-acceptance-"))
    dest = tmp / "s45-stories"
    shutil.copytree(PROJECT, dest, ignore=shutil.ignore_patterns(
        "__pycache__", ".git", ".venv", "venv", "archive"))
    (dest / "archive").mkdir(exist_ok=True)
    print(f"(running against a temp copy: {dest})")
    rc = subprocess.call([sys.executable, str(dest / "tools" / "acceptance.py"),
                          "--in-place"], cwd=str(dest))
    shutil.rmtree(tmp, ignore_errors=True)
    return rc


if "--in-place" not in sys.argv:
    raise SystemExit(run_in_copy())

sys.path.insert(0, str(PROJECT))

from PIL import Image  # noqa: E402

from s45core import core, render_engine, validate  # noqa: E402

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = ""):
    (PASS if cond else FAIL).append(name)
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f"\n         {detail}" if detail and not cond else ""))


def rules(issues):
    return {i["rule"] for i in validate.errors(issues)}


def base_config():
    return copy.deepcopy(core.load_config("inference-cost-is-not-cogs"))


def main() -> int:
    policy = core.load_policy()
    print("\n=== s45 acceptance checks ===\n")

    # ---------------------------------------------------------------- pixels
    print("Frames and layout")
    seq_dir = core.sequence_dir("inference-cost-is-not-cogs")
    frames = sorted(seq_dir.glob("frame_*.png"), key=core.frame_sort_key)
    check("every frame renders", len(frames) == 7, f"{len(frames)} frames")
    sizes = {Image.open(p).size for p in frames}
    check("every frame is 1080x1920", sizes == {(1080, 1920)}, str(sizes))

    if frames:
        im = Image.open(frames[0]).convert("L")
        ib = core.load_brand()["identity_block"]
        band = im.crop((ib["x"], ib["y"], 900, ib["y"] + 70))
        check("frame 1 carries the identity block (ink in the fixed band)",
              band.getextrema()[1] > 120, str(band.getextrema()))
        reserve = ib["reserve_band_to_y"]
        gap = im.crop((ib["x"], ib["y"] + 80, 1000, reserve - 20))
        check("the text stack does not collide with the identity block",
              gap.getextrema()[1] < 150, f"max luminance {gap.getextrema()[1]} in the gap")
        top_half = im.crop((0, 0, 1080, 960)).getextrema()[1]
        bottom = im.crop((0, 1400, 1080, 1920)).getextrema()[1]
        check("text sits high with background breathing below",
              top_half > bottom, f"top {top_half} vs bottom {bottom}")

        note = Image.open(core.sequence_dir("the-week-in-private-markets") /
                          "frame_1.png").convert("RGB")
        r, g, b = note.getpixel((20, 900))
        check("the field renders as the house teal, not the old near-black",
              g > r and g > 40 and b > 30, f"corner pixel {(r, g, b)}")
        check("the capital markets note fits above the footer rule",
              Image.open(core.sequence_dir("the-week-in-private-markets") /
                         "frame_1.png").convert("L")
              .crop((84, core.load_brand()["field"]["rule_y"] - 30,
                     1000, core.load_brand()["field"]["rule_y"] - 5))
              .getextrema()[1] < 150,
              "content is colliding with the footer rule")

    # determinism
    before = core.sha256_file(frames[2])
    render_engine.render_sequence("inference-cost-is-not-cogs", only_frame=3)
    after = core.sha256_file(frames[2])
    check("the renderer is deterministic (same config, same pixels)", before == after)

    # continuation frames: same ink rows, lower luminance, new text below
    def ink_rows(path, y0, y1, thresh=150):
        im = Image.open(path).convert("L").crop((84, y0, 1000, y1))
        rows = set()
        w = im.width
        px = im.load()
        for y in range(im.height):
            if any(px[x, y] > thresh for x in range(0, w, 3)):
                rows.add(y + y0)
        return rows

    r1 = ink_rows(seq_dir / "frame_1.png", 290, 560)
    r2 = ink_rows(seq_dir / "frame_2.png", 290, 560, thresh=90)
    overlap = len(r1 & r2) / max(1, len(r1))
    check("continuation frames redraw previous text at pixel-identical positions",
          overlap > 0.85, f"only {overlap:.0%} of the frame 1 text rows line up")

    lum1 = Image.open(seq_dir / "frame_1.png").convert("L").crop((84, 290, 900, 560))
    lum2 = Image.open(seq_dir / "frame_2.png").convert("L").crop((84, 290, 900, 560))
    check("previous text is dimmed on the continuation",
          sum(lum2.getdata()) < sum(lum1.getdata()),
          f"{sum(lum2.getdata())} should be < {sum(lum1.getdata())}")
    # measure below the drawn chrome - the S45 lockup is bright by design and sits
    # above every text band, so including it would answer a different question
    floor = render_engine.chrome_bottom(core.load_brand())
    bright = [y for y in ink_rows(seq_dir / "frame_2.png", floor, 1400, thresh=230)]
    check("the new beat lands bright below the dimmed setup",
          bool(bright) and min(bright) > max(ink_rows(seq_dir / "frame_1.png", floor, 1400)),
          f"bright rows start at {min(bright) if bright else None}")

    # ---------------------------------------------------------------- refusals
    print("\nValidation refusals")

    cfg = base_config()
    cfg["frames"][4]["blocks"][0]["text"] = "Frontier model pricing fell 90% in two years."
    cfg["frames"][4]["source_line"] = None
    check("a statistic without a source_line is refused",
          "statistic_requires_source" in rules(validate.validate_config(cfg, "x", policy)),
          str(rules(validate.validate_config(cfg, "x", policy))))

    cfg["frames"][4]["source_line"] = "Published provider list pricing, 2024 to 2026."
    check("the same statistic passes once it carries a source",
          "statistic_requires_source" not in rules(validate.validate_config(cfg, "x", policy)))

    for bad, label in [("NIFTY closed higher again this week.", "an index"),
                       ("The print on NSE: RELI says something.", "a ticker"),
                       ("A 3x return is not the point.", "a multiple")]:
        cfg = base_config()
        cfg["frames"][0]["blocks"][0]["text"] = bad
        r = rules(validate.validate_config(cfg, "x", policy))
        check(f"a config mentioning {label} is refused",
              bool(r & {"listed_security_scan", "banned_term"}), f"{bad!r} -> {r}")

    issues = validate.validate_config(
        {**base_config(), "frames": [{**base_config()["frames"][0],
                                      "blocks": [{"text": "NIFTY is up."}]}]}, "x", policy)
    quoted = [i["span"] for i in validate.errors(issues) if i["rule"] == "listed_security_scan"]
    check("the refusal quotes the offending span", quoted == ["NIFTY"], str(quoted))

    cfg = base_config()
    cfg["frames"][4]["artifact"] = "../../secret/client-screenshot.png"
    check("an artifact path outside assets/artifacts/ is refused",
          "artifact_path" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    del cfg["scope_attestation"]
    check("a missing scope_attestation is a hard failure",
          "scope_attestation" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["frames"][0]["blocks"][0]["highlights"] = [{"text": "Most diligence", "style": "underline"}]
    cfg["frames"][0]["blocks"][1]["highlights"] = [{"text": "more like R&D", "style": "underline"}]
    check("two highlights on one frame is refused",
          "one_highlight" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["frames"][0]["blocks"][1]["highlights"] = [{"text": "not in the text", "style": "underline"}]
    check("a highlight that is not a substring of its block is refused",
          "highlight_substring" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["frames"] = cfg["frames"][:3]
    check("a sequence outside 5 to 7 frames is refused",
          "frame_count" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["frames"][0]["background"] = {"type": "photo", "src": "desk-late-model-review.jpg"}
    check("a config still asking for a photo background is refused with a migration note",
          "background_photo_retired" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["frames"][0]["chart"] = {
        "type": "bar", "title": "t", "unit": "%",
        "labels": ["Q1", "Q2", "Q3"],
        "series": [{"values": [1, 2]}], "source": "s45."}
    check("a chart whose values do not line up with its labels is refused",
          "chart_series_length" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["frames"][0]["chart"] = {
        "type": "bar", "title": "t", "unit": "%", "labels": ["Q1", "Q2"],
        "series": [{"values": ["4", "6"]}], "source": "s45."}
    check("a chart carrying values as strings is refused",
          "chart_values" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["frames"][0]["chart"] = {
        "type": "bar", "title": "t", "unit": "%", "labels": ["Q1", "Q2"],
        "series": [{"values": [4, 6]}]}
    cfg["frames"][0]["source_line"] = None
    cfg["frames"][0].pop("data_sources", None)
    check("a chart with no source anywhere is refused",
          "statistic_requires_source" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["frames"][0]["metrics"] = [
        {"label": "Rounds", "value": "41", "delta": "-12% WoW"}]
    cfg["frames"][0]["source_line"] = "s45 deal tracker."
    check("a metric carrying a delta with no direction is refused",
          "metric_direction" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["frames"][0]["chart"] = {
        "type": "bar", "title": "t", "unit": "%", "labels": ["Q1", "Q2"],
        "series": [{"values": [4, 6]}], "source": "s45."}
    cfg["frames"][1]["continues"] = True
    check("a continuation after a chart frame is refused",
          "panel_not_continuable" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["type"] = "cta"
    cfg["ask"] = {"shape": "link", "destination": "somewhere-not-in-the-ledger",
                  "situation": "x"}
    cfg["frames"][-1]["role"] = "cta"
    check("an ask with no active entry in the ledger is refused",
          "ask_ledger" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["type"] = "cta"
    cfg["ask"] = {"shape": "link", "destination": "s45.example/research/ai-revenue-quality",
                  "situation": "x"}
    cfg["frames"][-1]["role"] = "cta"
    cfg["frames"][-1]["blocks"] = [{"text": "Reply with 'CONTENT' and I will send it over."}]
    check("a keyword-shaped ask is refused while keyword_ctas_allowed is false",
          "keyword_cta" in rules(validate.validate_config(cfg, "x", policy)))

    cfg = base_config()
    cfg["frames"][0]["blocks"][0]["text"] = "The print on RELIANCE says something."
    warn_rules = {i["rule"] for i in validate.warnings(validate.validate_config(cfg, "x", policy))}
    check("a bare all-caps name is flagged for review (warning, not a refusal)",
          "possible_listed_name" in warn_rules, str(warn_rules))

    # The asset cooldown retired with the photo library. Backgrounds are drawn from
    # brand.json, so there is no file to reuse and nothing to space out; what used to
    # be an asset-reuse risk is now a sameness risk, checked at batch level below.
    # ---------------------------------------------------------------- hard stop
    print("\nIdentity block hard stop")
    pol_backup = core.POLICY_PATH.read_text(encoding="utf-8")
    try:
        broken = json.loads(pol_backup)
        broken["sebi_registration_numbers"] = []
        core.write_json(core.POLICY_PATH, broken)
        try:
            render_engine.render_sequence("inference-cost-is-not-cogs")
            check("render refuses entirely while the registration fields are empty", False,
                  "it rendered anyway")
        except render_engine.RenderError as e:
            check("render refuses entirely while the registration fields are empty",
                  "identity_block_hard_stop" in str(e))
    finally:
        core.POLICY_PATH.write_text(pol_backup, encoding="utf-8")

    # ---------------------------------------------------------------- approval gate
    print("\nApproval gate")
    import schedule as schedule_mod

    slug = "inference-cost-is-not-cogs"
    ap = core.approval_path(slug)
    ap_backup = ap.read_text(encoding="utf-8") if ap.exists() else None
    sched_p = core.schedule_record_path(slug)
    sched_backup = sched_p.read_text(encoding="utf-8") if sched_p.exists() else None
    try:
        if ap.exists():
            ap.unlink()
        if sched_p.exists():
            sched_p.unlink()

        try:
            schedule_mod.check_publishable(slug, policy)
            check("schedule.py refuses an unapproved sequence", False, "it accepted it")
        except schedule_mod.Refusal as e:
            check("schedule.py refuses an unapproved sequence", "NOT PUBLISHABLE" in str(e))

        # a valid approval
        core.write_json(ap, {"slug": slug, "approver": policy["approvers"][0],
                             "approved_at": core.now_iso(), "author": "human",
                             "frame_hashes": core.frame_hashes(core.sequence_dir(slug))})
        try:
            schedule_mod.check_publishable(slug, policy)
            check("schedule.py accepts a properly approved sequence", True)
        except schedule_mod.Refusal as e:
            check("schedule.py accepts a properly approved sequence", False, str(e))

        # a frame changed after approval
        target = core.sequence_dir(slug) / "frame_3.png"
        original = target.read_bytes()
        im = Image.open(target)
        im.putpixel((5, 5), (255, 0, 0))
        im.save(target)
        try:
            schedule_mod.check_publishable(slug, policy)
            check("a frame changed after approval invalidates the approval", False)
        except schedule_mod.Refusal as e:
            check("a frame changed after approval invalidates the approval",
                  "APPROVAL INVALIDATED" in str(e))
        target.write_bytes(original)

        # an agent-written approval
        core.write_json(ap, {"slug": slug, "approver": policy["approvers"][0],
                             "approved_at": core.now_iso(), "author": "claude",
                             "frame_hashes": core.frame_hashes(core.sequence_dir(slug))})
        try:
            schedule_mod.check_publishable(slug, policy)
            check("an agent-written approval is invalid", False)
        except schedule_mod.Refusal as e:
            check("an agent-written approval is invalid", "INVALID APPROVAL" in str(e))

        # an unknown approver
        core.write_json(ap, {"slug": slug, "approver": "someone@random.example",
                             "approved_at": core.now_iso(), "author": "human",
                             "frame_hashes": core.frame_hashes(core.sequence_dir(slug))})
        try:
            schedule_mod.check_publishable(slug, policy)
            check("an approver outside policy.approvers is refused", False)
        except schedule_mod.Refusal as e:
            check("an approver outside policy.approvers is refused",
                  "not in policy.approvers" in str(e))

        # hand-post refusal on the cta sequence
        cta = "the-one-page-before-a-mandate"
        cta_ap = core.approval_path(cta)
        core.write_json(cta_ap, {"slug": cta, "approver": policy["approvers"][0],
                                 "approved_at": core.now_iso(), "author": "human",
                                 "frame_hashes": core.frame_hashes(core.sequence_dir(cta))})
        try:
            schedule_mod.check_publishable(cta, policy)
            check("schedule.py refuses a sequence with a hand-post-only frame", False)
        except schedule_mod.Refusal as e:
            check("schedule.py refuses a sequence with a hand-post-only frame",
                  "HAND-POST ONLY" in str(e))
        cta_ap.unlink()
    finally:
        if ap_backup is not None:
            ap.write_text(ap_backup, encoding="utf-8")
        elif ap.exists():
            ap.unlink()
        if sched_backup is not None:
            sched_p.write_text(sched_backup, encoding="utf-8")
        elif sched_p.exists():
            sched_p.unlink()

    # ---------------------------------------------------------------- post-order
    print("\nPost order and week check")
    pol = core.load_policy()
    ap = core.approval_path(slug)
    saved = ap.read_text(encoding="utf-8") if ap.exists() else None
    try:
        if ap.exists():
            ap.unlink()
        po = render_engine.write_post_order(slug, core.load_config(slug), pol) \
            .read_text(encoding="utf-8")
        check("post-order.md states an unapproved sequence is unapproved", "UNAPPROVED" in po)
        check("post-order.md confirms frame 1 carries the identity block",
              "Frame 1 carries the identity block: **yes**" in po)
        check("post-order.md says to push all frames as one story post",
              "ONE story post" in po)
    finally:
        if saved is not None:
            ap.write_text(saved, encoding="utf-8")
        po2 = render_engine.write_post_order(slug, core.load_config(slug), pol) \
            .read_text(encoding="utf-8")
        check("post-order.md flips to 'approval on file' once approved",
              saved is None or "Approval on file" in po2)

    po_cta = (core.sequence_dir("the-one-page-before-a-mandate") / "post-order.md")
    check("post-order.md names the hand-post-only frames",
          "Hand-post-only frames" in po_cta.read_text(encoding="utf-8"))

    slugs = core.list_sequence_slugs()
    week = validate.check_week(slugs, pol)
    check("the shipped week cross-validates clean",
          not validate.errors(week), validate.format_issues(week))

    # a second sequence opening on the first one's headline
    twin = core.sequence_dir("acceptance-twin")
    twin.mkdir(parents=True, exist_ok=True)
    tcfg = base_config()
    tcfg["slug"] = "acceptance-twin"
    core.write_json(twin / "config.json", tcfg)
    dup = validate.check_week(slugs + ["acceptance-twin"], pol)
    check("--check-week catches two sequences opening on the same headline",
          "duplicate_headline" in {i["rule"] for i in validate.errors(dup)},
          validate.format_issues(dup))

    charted = [s for s in slugs
               if any(f.get("chart") for f in core.load_config(s).get("frames", []))]
    chart_week = list(charted)
    for i in range(3 - len(charted)):
        name = f"acceptance-chart-{i}"
        d = core.sequence_dir(name)
        d.mkdir(parents=True, exist_ok=True)
        ccfg = copy.deepcopy(core.load_config(charted[0]))
        ccfg["slug"] = name
        ccfg["frames"][0]["blocks"][0]["text"] = f"A distinct opening line, number {i}."
        core.write_json(d / "config.json", ccfg)
        chart_week.append(name)
    charty = validate.check_week(chart_week, pol)
    check("--check-week warns when every sequence in the week leans on a chart",
          "chart_monotony" in {i["rule"] for i in validate.warnings(charty)},
          validate.format_issues(charty))

    ctas = [s for s in slugs if core.load_config(s).get("type") == "cta"]
    tcfg2 = copy.deepcopy(core.load_config(ctas[0]))
    tcfg2["slug"] = "acceptance-twin"
    core.write_json(twin / "config.json", tcfg2)
    dup2 = validate.check_week(ctas + ["acceptance-twin"], pol)
    check("--check-week catches two cta sequences in one week",
          "cta_rhythm" in {i["rule"] for i in validate.errors(dup2)})
    check("--check-week catches a duplicate ask destination",
          "duplicate_ask" in {i["rule"] for i in validate.errors(dup2)})
    shutil.rmtree(twin, ignore_errors=True)

    # ---------------------------------------------------------------- summary
    print(f"\n{'-' * 60}")
    print(f"  {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        for f in FAIL:
            print(f"    FAILED: {f}")
    print(f"{'-' * 60}\n")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
