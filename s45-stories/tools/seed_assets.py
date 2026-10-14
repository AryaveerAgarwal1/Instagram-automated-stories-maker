#!/usr/bin/env python3
"""Generate placeholder artifact pages so the system renders on first run.

There is no photography in this project any more. Backgrounds are *drawn* from
`config/brand.json` - the deep teal field with its grid, the S45 mark and the
kicker - so there is nothing to seed for them and nothing to keep in sync.

Artifacts are still real files, because a redacted memo page is a document, not a
style. The ones written here are synthetic stand-ins labelled as such. Replace
`assets/artifacts/` with genuine redacted pages before anything goes out.

    python tools/seed_assets.py [--force]
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from s45core import core  # noqa: E402

ARTIFACTS = [
    ("diligence-margin-page-redacted.png",
     "redacted margin analysis page from the diligence template"),
    ("memo-structure-outline.png",
     "the structure we use for an information memorandum, no client content"),
    ("model-three-price-cases.png",
     "unit economics at three model prices, structure only"),
    ("checklist-ai-revenue.png",
     "the AI-native revenue quality checklist, page one"),
]


def font(size, bold=False):
    p = core.FONTS_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    try:
        return ImageFont.truetype(str(p), size)
    except OSError:
        return ImageFont.load_default()


def make_artifact(name: str, desc: str) -> Image.Image:
    w, h = 900, 1160
    img = Image.new("RGB", (w, h), (243, 241, 236))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 96], fill=(228, 224, 216))
    d.text((44, 34), "s45  -  internal template  -  redacted", font=font(26, True),
           fill=(70, 68, 64))

    y = 150
    rnd = random.Random(hash(name) & 0xFFFF)
    d.text((44, y), desc[:46], font=font(30, True), fill=(40, 40, 40))
    y += 70
    for row in range(20):
        wgt = rnd.uniform(0.35, 0.95)
        d.rectangle([44, y, 44 + int((w - 120) * wgt), y + 12], fill=(206, 202, 195))
        if row % 5 == 4:
            d.rectangle([44, y + 26, 44 + 260, y + 38], fill=(200, 216, 168))
            y += 26
        y += 42
    d.text((44, h - 76), "REDACTED PLACEHOLDER - nothing client-identifying",
           font=font(24), fill=(120, 140, 90))
    return img


def write_index(folder: Path, rows: list[tuple[str, str]], title: str, note: str):
    lines = [f"# {title}", "", note, ""]
    for name, desc in rows:
        lines.append(f"- `{name}` - {desc}")
    lines.append("")
    (folder / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    core.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    for name, desc in ARTIFACTS:
        out = core.ARTIFACTS_DIR / name
        if out.exists() and not args.force:
            continue
        make_artifact(name, desc).save(out)
        print(f"  wrote assets/artifacts/{name}")

    write_index(
        core.ARTIFACTS_DIR, ARTIFACTS, "Artifacts",
        "Redacted memo pages, model structures, checklist pages, framework sketches.\n\n"
        "**Redacted before they enter this folder; originals stored somewhere else "
        "entirely.** Nothing client-identifying ever lands here. The renderer will only "
        "composite filenames from this folder - that restriction is the structural block "
        "on a client screenshot ever reaching a frame.\n\n"
        "There is no `assets/backgrounds/` folder. Backgrounds are drawn from "
        "`config/brand.json`, so a frame reproduces from its config and the brand file "
        "alone - no photo library to keep, no cooldown to police.",
    )
    print("  wrote assets/artifacts/INDEX.md")


if __name__ == "__main__":
    main()
