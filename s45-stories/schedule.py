#!/usr/bin/env python3
"""schedule.py - the publisher. Refuses anything the approval gate has not cleared.

    python schedule.py sequences/<slug>
    python schedule.py sequences/<slug> --dry-run

Refusals, in order:
  1. no approval.json                       -> not publishable, full stop
  2. approver not in policy.approvers       -> invalid approval
  3. any frame hash differs from approval   -> a frame changed after sign-off
  4. sequence contains a hand-post-only frame -> three minutes in the app
  5. already published                      -> no double-posting

On success it records what it pushed, stamps the asset cooldown ledger, and tells
you to run archive.py.

The actual Instagram push is left as one clearly marked function. Wire it to
whichever Graph API / scheduling tool s45 uses. Everything above it is the part
that must not be bypassed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from s45core import core


class Refusal(RuntimeError):
    pass


def check_publishable(slug: str, policy: dict) -> dict:
    seq = core.sequence_dir(slug)
    cfg = core.load_config(slug)

    ap = core.approval_path(slug)
    if not ap.exists():
        raise Refusal(
            f"{slug}: NOT PUBLISHABLE. sequences/{slug}/approval.json does not exist.\n"
            "  A rendered sequence is not publishable until a named human signs off on "
            "the exact pixels.\n"
            "  Claude never writes approval.json. Approval is the approver's."
        )

    approval = core.read_json(ap)

    approver = approval.get("approver")
    if approver not in (policy.get("approvers") or []):
        raise Refusal(
            f"{slug}: INVALID APPROVAL. approver {approver!r} is not in policy.approvers "
            f"{policy.get('approvers')}."
        )

    if approval.get("approved_by_agent") or approval.get("author") == "claude":
        raise Refusal(
            f"{slug}: INVALID APPROVAL. approval.json is marked as agent-written. "
            "The approval artifact must never be writable by the thing that generated "
            "the content."
        )

    current = core.frame_hashes(seq)
    recorded = approval.get("frame_hashes") or {}
    if not recorded:
        raise Refusal(f"{slug}: INVALID APPROVAL. no frame hashes recorded.")

    if current != recorded:
        changed = sorted(set(current) ^ set(recorded)) or [
            k for k in current if current.get(k) != recorded.get(k)
        ]
        raise Refusal(
            f"{slug}: APPROVAL INVALIDATED. frame(s) {', '.join(changed)} changed after "
            "approval.\n  Re-render, then re-approve. The approval is bound to the pixels."
        )

    hand = core.hand_post_frames(cfg)
    if hand:
        raise Refusal(
            f"{slug}: HAND-POST ONLY. frame(s) {', '.join(str(h) for h in hand)} need a "
            "native sticker or link.\n"
            "  Auto-published stories have no native stickers, no tappable links, no "
            "music.\n"
            "  Post this one by hand, then record it with:  "
            f"python schedule.py sequences/{slug} --mark-hand-posted"
        )

    rec = core.read_json(core.schedule_record_path(slug), default=None)
    if rec and rec.get("published_at"):
        raise Refusal(
            f"{slug}: ALREADY PUBLISHED at {rec['published_at']}. Refusing to double-post."
        )

    return {"config": cfg, "approval": approval, "frames": current}


# --------------------------------------------------------------------------
# the actual push - wire this to the s45 publishing tool
# --------------------------------------------------------------------------

def push_story(slug: str, cfg: dict, frame_paths: list[Path], dry_run: bool) -> dict:
    """Push all frames as ONE story post carrying the images in order.

    Never N separate posts: separate posts publish out of order and a scrambled
    argument is worse than none.
    """
    if dry_run:
        return {"mode": "dry-run", "pushed": [p.name for p in frame_paths]}
    # ---- integration point -------------------------------------------
    # e.g. instagram_graph.create_story_carousel(frame_paths, ...)
    # Deliberately unimplemented: the gate above is the part that matters.
    raise NotImplementedError(
        "push_story() is the integration point. Wire it to the s45 publishing tool, "
        "or run with --dry-run / --mark-hand-posted while hand-posting."
    )


def record(slug: str, cfg: dict, frames: dict, mode: str, note: str = "") -> None:
    srcs = [f["background"]["src"] for f in cfg.get("frames", [])
            if (f.get("background") or {}).get("type") == "photo"
            and (f.get("background") or {}).get("src")]

    core.write_json(core.schedule_record_path(slug), {
        "slug": slug,
        "published_at": core.now_iso(),
        "mode": mode,
        "note": note,
        "highlight_title": cfg.get("highlight_title"),
        "frame_hashes": frames,
        "assets_used": srcs,
    })
    core.record_asset_use(srcs, slug)


def main() -> int:
    ap = argparse.ArgumentParser(description="s45 story publisher (approval-gated)")
    ap.add_argument("target", help="sequences/<slug>")
    ap.add_argument("--dry-run", action="store_true",
                    help="run every gate, push nothing")
    ap.add_argument("--mark-hand-posted", action="store_true",
                    help="record a sequence you posted by hand (still gated on approval)")
    args = ap.parse_args()

    slug = Path(args.target.rstrip("/\\")).name
    policy = core.load_policy()

    try:
        if args.mark_hand_posted:
            # everything except the hand-post refusal
            seq = core.sequence_dir(slug)
            cfg = core.load_config(slug)
            approval = core.read_json(core.approval_path(slug), default=None)
            if not approval:
                raise Refusal(f"{slug}: NOT PUBLISHABLE. no approval.json.")
            if approval.get("approver") not in (policy.get("approvers") or []):
                raise Refusal(f"{slug}: INVALID APPROVAL. approver not in policy.approvers.")
            if core.frame_hashes(seq) != (approval.get("frame_hashes") or {}):
                raise Refusal(f"{slug}: APPROVAL INVALIDATED. frames changed after approval.")
            rec = core.read_json(core.schedule_record_path(slug), default=None)
            if rec and rec.get("published_at"):
                raise Refusal(f"{slug}: ALREADY PUBLISHED at {rec['published_at']}.")
            record(slug, cfg, core.frame_hashes(seq), "hand-posted")
            print(f"OK  {slug}: recorded as hand-posted. Now run:  "
                  f"python archive.py sequences/{slug}")
            return 0

        state = check_publishable(slug, policy)
    except Refusal as e:
        print(f"\nREFUSED\n{e}\n", file=sys.stderr)
        return 1

    seq = core.sequence_dir(slug)
    paths = sorted(seq.glob("frame_*.png"), key=core.frame_sort_key)
    result = push_story(slug, state["config"], paths, args.dry_run)

    if args.dry_run:
        print(f"OK  {slug}: every gate passed. Would push {len(paths)} frames as one "
              f"story post, in order.")
        print(f"    approved by {state['approval']['approver']} at "
              f"{state['approval'].get('approved_at')}")
        print("    dry run - nothing published, ledgers untouched.")
        return 0

    record(slug, state["config"], state["frames"], result.get("mode", "scheduled"))
    print(f"OK  {slug}: published. Run  python archive.py sequences/{slug}  now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
