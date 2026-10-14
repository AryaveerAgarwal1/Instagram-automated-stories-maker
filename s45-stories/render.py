#!/usr/bin/env python3
"""render.py - the deterministic renderer.

    python render.py sequences/<slug>            render all frames
    python render.py sequences/<slug> --frame 4  re-render frame 4 + its continuations
    python render.py sequences/<slug> --validate check without rendering
    python render.py --check-week sequences/     cross-validate a batch
    python render.py --all                       render every sequence
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from s45core import core, render_engine, validate


def slug_from_arg(arg: str) -> str:
    p = Path(arg.rstrip("/\\"))
    return p.name


def cmd_validate(slug: str, policy) -> int:
    cfg = core.load_config(slug)
    issues = validate.validate_config(cfg, slug, policy)
    errs = validate.errors(issues)
    print(validate.format_issues(issues, slug))
    return 1 if errs else 0


def cmd_render(slug: str, frame: int | None, policy, brand) -> int:
    try:
        res = render_engine.render_sequence(slug, only_frame=frame, policy=policy, brand=brand)
    except render_engine.RenderError as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1
    for w in res["warnings"]:
        print(f"  warning: {w}")
    print(f"OK  {slug}: wrote {', '.join(res['frames'])}")
    print(f"    {res['post_order']}")
    if not core.approval_path(slug).exists():
        print("    UNAPPROVED - schedule.py will refuse this sequence until "
              "approval.json exists.")
    return 0


def cmd_check_week(folder: str, policy) -> int:
    root = Path(folder)
    slugs = sorted(d.name for d in root.iterdir()
                   if d.is_dir() and (d / "config.json").exists())
    rc = 0
    for s in slugs:
        rc |= cmd_validate(s, policy)
    print("\n-- batch --")
    issues = validate.check_week(slugs, policy)
    if issues:
        print(validate.format_issues(issues, "week"))
        if validate.errors(issues):
            rc = 1
    else:
        print(f"OK  {len(slugs)} sequences, no duplicate headlines, no duplicate asks")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description="s45 story renderer")
    ap.add_argument("target", nargs="?", help="sequences/<slug>")
    ap.add_argument("--frame", type=int, default=None,
                    help="re-render one frame plus its continuations")
    ap.add_argument("--validate", action="store_true", help="check without rendering")
    ap.add_argument("--check-week", metavar="FOLDER",
                    help="cross-validate a batch for asset reuse and duplicate asks")
    ap.add_argument("--all", action="store_true", help="render every sequence")
    args = ap.parse_args()

    policy = core.load_policy()
    brand = core.load_brand()

    ok, why = core.policy_registration_ready(policy)
    if not ok:
        print("=" * 72)
        print("HARD STOP - the identity block never degrades.")
        print(f"  {why}")
        print("  Fill config/policy.json with the SEBI-registered name and")
        print("  registration number, exactly as registered, before rendering.")
        print("=" * 72)
        if not args.validate and not args.check_week:
            return 2

    if str(policy.get("entity_status")) == "TBD_BY_COUNSEL":
        print("warning: entity_status is TBD_BY_COUNSEL. Q1 and Q2 in the skill file "
              "must be answered by Indian counsel before the first post.\n")

    if args.check_week:
        return cmd_check_week(args.check_week, policy)

    if args.all:
        rc = 0
        for s in core.list_sequence_slugs():
            rc |= (cmd_validate(s, policy) if args.validate
                   else cmd_render(s, None, policy, brand))
        return rc

    if not args.target:
        ap.print_help()
        return 2

    slug = slug_from_arg(args.target)
    if not (core.sequence_dir(slug) / "config.json").exists():
        print(f"no config at sequences/{slug}/config.json", file=sys.stderr)
        return 2

    if args.validate:
        return cmd_validate(slug, policy)
    return cmd_render(slug, args.frame, policy, brand)


if __name__ == "__main__":
    raise SystemExit(main())
