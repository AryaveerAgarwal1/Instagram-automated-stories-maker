"""Paths, config loading, ledgers, hashing. No Pillow here - importable anywhere."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CONFIG_DIR = ROOT / "config"
ASSETS_DIR = ROOT / "assets"
ARTIFACTS_DIR = ASSETS_DIR / "artifacts"
FONTS_DIR = ASSETS_DIR / "fonts"
LEDGERS_DIR = ROOT / "ledgers"
SEQUENCES_DIR = ROOT / "sequences"
ARCHIVE_DIR = ROOT / "archive"
PROMPTS_DIR = ROOT / "prompts"

POLICY_PATH = CONFIG_DIR / "policy.json"
BRAND_PATH = CONFIG_DIR / "brand.json"
ASSET_USAGE_PATH = LEDGERS_DIR / "asset-usage.json"
ASKS_PATH = LEDGERS_DIR / "asks.json"
IDEAS_PATH = LEDGERS_DIR / "ideas.json"

VALID_TYPES = {"private_markets", "thesis", "build", "cta"}
VALID_SIZES = {"big", "med", "small"}
VALID_HIGHLIGHT_STYLES = {"underline", "text", "strike"}
VALID_TEXT_POSITIONS = {"top", "center", "bottom"}
VALID_BACKGROUND_TYPES = {"field", "note"}
VALID_CHART_TYPES = {"bar", "line"}
VALID_DELTA_DIRECTIONS = {"up", "down", "flat"}
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

PLACEHOLDER_MARKER = "PLACEHOLDER"


# --------------------------------------------------------------------------
# json helpers
# --------------------------------------------------------------------------

_MISSING = object()


def read_json(path: Path, default=_MISSING):
    p = Path(path)
    if not p.exists():
        if default is not _MISSING:
            return default
        raise FileNotFoundError(f"missing file: {p}")
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, p)


def load_policy() -> dict:
    return read_json(POLICY_PATH)


def load_brand() -> dict:
    return read_json(BRAND_PATH)


# --------------------------------------------------------------------------
# time
# --------------------------------------------------------------------------

def today() -> date:
    return datetime.now(timezone.utc).date()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_day(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


# --------------------------------------------------------------------------
# hashing
# --------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def frame_hashes(seq_dir: Path) -> dict:
    """{'frame_1.png': '<sha256>', ...} in frame order."""
    out = {}
    for p in sorted(Path(seq_dir).glob("frame_*.png"), key=frame_sort_key):
        out[p.name] = sha256_file(p)
    return out


def frame_sort_key(p: Path) -> int:
    try:
        return int(p.stem.split("_")[1])
    except (IndexError, ValueError):
        return 0


# --------------------------------------------------------------------------
# sequences
# --------------------------------------------------------------------------

def sequence_dir(slug: str) -> Path:
    slug = str(slug).strip().strip("/")
    if not slug or "/" in slug or "\\" in slug or slug.startswith("."):
        raise ValueError(f"unsafe slug: {slug!r}")
    return SEQUENCES_DIR / slug


def load_config(slug: str) -> dict:
    return read_json(sequence_dir(slug) / "config.json")


def list_sequence_slugs() -> list[str]:
    if not SEQUENCES_DIR.exists():
        return []
    return sorted(
        d.name for d in SEQUENCES_DIR.iterdir()
        if d.is_dir() and (d / "config.json").exists()
    )


def approval_path(slug: str) -> Path:
    return sequence_dir(slug) / "approval.json"


def schedule_record_path(slug: str) -> Path:
    return sequence_dir(slug) / "schedule.json"


def sequence_status(slug: str) -> dict:
    """Cheap status summary used by the UI and by schedule.py."""
    d = sequence_dir(slug)
    cfg = read_json(d / "config.json", default={})
    frames = sorted(d.glob("frame_*.png"), key=frame_sort_key)
    approval = read_json(approval_path(slug), default=None)
    sched = read_json(schedule_record_path(slug), default=None)

    approval_state = "unapproved"
    if approval:
        approval_state = "approved"
        try:
            if frame_hashes(d) != approval.get("frame_hashes", {}):
                approval_state = "stale"
        except OSError:
            approval_state = "stale"

    if sched and sched.get("published_at"):
        state = "published"
    elif approval_state == "approved":
        state = "approved"
    elif approval_state == "stale":
        state = "approval_stale"
    elif frames:
        state = "rendered"
    else:
        state = "draft"

    return {
        "slug": slug,
        "type": cfg.get("type"),
        "highlight_title": cfg.get("highlight_title"),
        "frame_count": len(cfg.get("frames", [])),
        "rendered_frames": [p.name for p in frames],
        "state": state,
        "approval": approval,
        "approval_state": approval_state,
        "schedule": sched,
        "hand_post_only": hand_post_frames(cfg),
    }


def hand_post_frames(cfg: dict) -> list[int]:
    """Ask frames and any frame carrying a sticker are hand-post only."""
    out = []
    for fr in cfg.get("frames", []):
        if fr.get("role") == "cta" or fr.get("sticker"):
            out.append(fr.get("n"))
    return out


# --------------------------------------------------------------------------
# ledgers
# --------------------------------------------------------------------------

def load_asset_usage() -> dict:
    return read_json(ASSET_USAGE_PATH, default={"assets": {}})


def save_asset_usage(data: dict) -> None:
    write_json(ASSET_USAGE_PATH, data)


def asset_last_used(src: str, usage: dict | None = None):
    usage = usage if usage is not None else load_asset_usage()
    entry = usage.get("assets", {}).get(src)
    if not entry:
        return None
    return parse_day(entry.get("last_used"))


def asset_cooldown_remaining(src: str, policy: dict, usage: dict | None = None) -> int:
    """Days left before src may be used again. 0 means free."""
    last = asset_last_used(src, usage)
    if last is None:
        return 0
    window = int(policy.get("asset_cooldown_days", 14))
    free_on = last + timedelta(days=window)
    return max(0, (free_on - today()).days)


def record_asset_use(srcs, slug: str, when: date | None = None) -> None:
    """Called on PUBLISH, not on render. Cooldown tracks what went out."""
    usage = load_asset_usage()
    usage.setdefault("assets", {})
    stamp = (when or today()).isoformat()
    for src in srcs:
        entry = usage["assets"].setdefault(src, {"last_used": None, "history": []})
        entry["last_used"] = stamp
        entry["history"].append({"slug": slug, "date": stamp})
        entry["history"] = entry["history"][-40:]
    save_asset_usage(usage)


def load_asks() -> dict:
    return read_json(ASKS_PATH, default={"asks": []})


def active_asks() -> list[dict]:
    return [a for a in load_asks().get("asks", []) if a.get("status") == "active"]


def load_ideas() -> dict:
    return read_json(IDEAS_PATH, default={"ideas": []})


def save_ideas(data: dict) -> None:
    write_json(IDEAS_PATH, data)


# --------------------------------------------------------------------------
# assets
# --------------------------------------------------------------------------

def resolve_background(src: str, slug: str | None = None) -> Path | None:
    """Retired. There are no photo backgrounds - every frame is drawn from brand.json.

    Kept as a stub so archive.py and server/app.py fail loudly rather than silently
    if a config from before the teal template still names a photo."""
    return None


def resolve_artifact(src: str) -> Path | None:
    """assets/artifacts/ ONLY. Structural block on a client screenshot reaching a frame."""
    if not src:
        return None
    name = Path(str(src)).name
    if name != str(src):
        return None
    p = (ARTIFACTS_DIR / name).resolve()
    try:
        p.relative_to(ARTIFACTS_DIR.resolve())
    except ValueError:
        return None
    return p if p.exists() else None


def list_backgrounds() -> list[str]:
    """No photo library any more. The UI shows background *styles*, not files."""
    return []


def list_artifacts() -> list[str]:
    if not ARTIFACTS_DIR.exists():
        return []
    return sorted(
        p.name for p in ARTIFACTS_DIR.iterdir()
        if p.suffix.lower() in PHOTO_EXTS
    )


def read_index(folder: Path) -> dict:
    """Parse INDEX.md lines of the form `filename.jpg - description`."""
    idx = folder / "INDEX.md"
    out = {}
    if not idx.exists():
        return out
    for line in idx.read_text(encoding="utf-8").splitlines():
        line = line.strip().lstrip("-").strip()
        if " - " in line or " — " in line:
            sep = " - " if " - " in line else " — "
            name, desc = line.split(sep, 1)
            name = name.strip().strip("`")
            if Path(name).suffix.lower() in PHOTO_EXTS:
                out[name] = desc.strip()
    return out


def policy_registration_ready(policy: dict) -> tuple[bool, str]:
    """The identity block hard stop."""
    if not policy.get("identity_block_required"):
        return True, ""
    name = (policy.get("sebi_registered_name") or "").strip()
    nums = [str(n).strip() for n in policy.get("sebi_registration_numbers") or [] if str(n).strip()]
    if not name:
        return False, "policy.sebi_registered_name is unset"
    if not nums:
        return False, "policy.sebi_registration_numbers is empty"
    if PLACEHOLDER_MARKER in name.upper() or any(PLACEHOLDER_MARKER in n.upper() for n in nums):
        return False, (
            "policy.json still carries PLACEHOLDER registration values. "
            "Get counsel to answer Q1 and Q2, then replace them. "
            "The identity block never degrades - this is a hard stop, not a warning."
        )
    return True, ""


def identity_block_lines(policy: dict) -> list[str]:
    name = (policy.get("sebi_registered_name") or "").strip()
    nums = [str(n).strip() for n in policy.get("sebi_registration_numbers") or []]
    lines = [name]
    if nums:
        lines.append("SEBI Reg. " + " / ".join(nums))
    return [ln for ln in lines if ln]
