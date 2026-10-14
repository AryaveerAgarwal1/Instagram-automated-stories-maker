#!/usr/bin/env python3
"""archive.py - the immutable publication record.

    python archive.py sequences/<slug>

Copies frames, config, approval and schedule record into archive/<yyyy-mm-dd>/<slug>/
with a SHA-256 manifest, write-once. Retained for policy.retention_days.

Because the renderer is deterministic, the archived config plus the archived assets
reproduce the exact published pixels - a stronger record than storing images alone,
and the thing you will want if anyone ever asks what s45 published on a given day.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import timedelta
from pathlib import Path

from s45core import core


def archive_sequence(slug: str, force: bool = False) -> Path:
    seq = core.sequence_dir(slug)
    cfg = core.load_config(slug)
    policy = core.load_policy()

    sched = core.read_json(core.schedule_record_path(slug), default=None)
    if not sched or not sched.get("published_at"):
        raise RuntimeError(
            f"{slug}: nothing to archive. The archive records what was published; "
            "publish it first (schedule.py) or mark it hand-posted."
        )

    day = core.parse_day(sched["published_at"]) or core.today()
    dest = core.ARCHIVE_DIR / day.isoformat() / slug

    if dest.exists() and not force:
        raise RuntimeError(
            f"{slug}: {dest.relative_to(core.ROOT)} already exists. The archive is "
            "write-once. Use --force only if you know why."
        )

    (dest / "assets").mkdir(parents=True, exist_ok=True)

    manifest = {
        "slug": slug,
        "archived_at": core.now_iso(),
        "published_at": sched["published_at"],
        "publish_mode": sched.get("mode"),
        "retention_days": policy.get("retention_days"),
        "retain_until": (day + timedelta(days=int(policy.get("retention_days", 3650)))).isoformat(),
        "policy_snapshot": {
            "entity_status": policy.get("entity_status"),
            "sebi_registered_name": policy.get("sebi_registered_name"),
            "sebi_registration_numbers": policy.get("sebi_registration_numbers"),
            "disclosure_lines": policy.get("disclosure_lines"),
        },
        "files": {},
    }

    def copy_in(src: Path, rel: str):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        manifest["files"][rel] = core.sha256_file(target)

    for p in sorted(seq.glob("frame_*.png"), key=core.frame_sort_key):
        copy_in(p, p.name)
    for name in ("config.json", "approval.json", "schedule.json", "post-order.md"):
        p = seq / name
        if p.exists():
            copy_in(p, name)

    # archive the source assets too - deterministic render needs them to reproduce.
    # Backgrounds are drawn from brand.json, so config.json + brand.json is the
    # whole reproduction input for them. Artifacts are files and must be copied.
    copy_in(core.BRAND_PATH, "assets/brand.json")
    for fr in cfg.get("frames", []):
        if fr.get("artifact"):
            rp = core.resolve_artifact(fr["artifact"])
            if rp:
                copy_in(rp, f"assets/{rp.name}")

    core.write_json(dest / "manifest.json", manifest)

    # write-once, best effort on the local filesystem
    for p in dest.rglob("*"):
        if p.is_file():
            try:
                p.chmod(0o444)
            except OSError:
                pass

    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description="s45 publication archive")
    ap.add_argument("target", help="sequences/<slug>")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    slug = Path(args.target.rstrip("/\\")).name
    try:
        dest = archive_sequence(slug, args.force)
    except (RuntimeError, FileNotFoundError) as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1
    print(f"OK  archived to {dest.relative_to(core.ROOT)} with a SHA-256 manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
