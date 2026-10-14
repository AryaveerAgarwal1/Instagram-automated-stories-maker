"""The deterministic renderer. Pillow only.

Same config in, same pixels out. No AI at render time, no network at render time.
Every published frame is reproducible from its config months later, which is what a
retention obligation needs.

Backgrounds are *drawn*, not photographed. The whole visual system is the deep teal
capital-markets-note field defined in `config/brand.json`: graph-paper grid, the S45
mark, a kicker rule, and a two-column footer. That means a frame reproduces from
`config.json` + `brand.json` alone - there is no photo library to archive, no asset
cooldown to police, and no chance of a stale image file changing what a published
frame looked like.

Charts are drawn the same way: from numbers Claude wrote into the config, never from
a live feed. A frame that fetched data at render time could not be re-rendered
identically, and that is the one property this system cannot give up.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field as dc_field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import core, validate

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (str(path), int(size))
    if key not in _FONT_CACHE:
        p = Path(path)
        if not p.is_absolute():
            p = core.ROOT / p
        try:
            _FONT_CACHE[key] = ImageFont.truetype(str(p), int(size))
        except OSError:
            _FONT_CACHE[key] = ImageFont.load_default()
    return _FONT_CACHE[key]


def brand_font(brand: dict, key: str, size_key: str) -> ImageFont.FreeTypeFont:
    return get_font(brand["fonts"][key], brand["type_scale"][size_key])


def rgba(color, alpha=None):
    c = list(color)
    if len(c) == 3:
        c.append(255 if alpha is None else alpha)
    elif alpha is not None:
        c[3] = alpha
    return tuple(int(v) for v in c)


def measure(text: str, font) -> tuple[int, int]:
    box = font.getbbox(text)
    return box[2] - box[0], box[3] - box[1]


def tracked_width(text: str, font, tracking: int) -> int:
    if not text:
        return 0
    return sum(measure(ch, font)[0] for ch in text) + tracking * (len(text) - 1)


def draw_tracked(d: ImageDraw.ImageDraw, xy, text: str, font, fill, tracking: int = 0):
    """Letter-spaced text. The mono labels in the house style are tracked out;
    Pillow has no tracking, so glyphs are placed one at a time."""
    if not tracking:
        d.text(xy, text, font=font, fill=fill)
        return measure(text, font)[0]
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += measure(ch, font)[0] + tracking
    return int(x - xy[0] - tracking)


# --------------------------------------------------------------------------
# text layout
# --------------------------------------------------------------------------

@dataclass
class LineItem:
    text: str
    x: int
    y: int
    font_path: str
    font_size: int
    hl_start: int = -1      # char offset inside this line
    hl_end: int = -1
    hl_style: str = ""
    tone: str = "primary"   # "primary" | "accent" - the two-tone headline

    @property
    def font(self):
        return get_font(self.font_path, self.font_size)


@dataclass
class TextStack:
    items: list[LineItem] = dc_field(default_factory=list)
    top: int = 0
    bottom: int = 0


def wrap_with_offsets(text: str, font, max_w: int):
    """Greedy wrap. Returns [(line_text, start_offset, end_offset)] into the
    whitespace-normalised source text."""
    norm = " ".join(str(text).split())
    words = norm.split(" ")
    lines, cur, cur_start, cursor = [], "", 0, 0
    for w in words:
        trial = w if not cur else cur + " " + w
        if measure(trial, font)[0] <= max_w or not cur:
            cur = trial
        else:
            lines.append((cur, cur_start, cur_start + len(cur)))
            cur_start = cursor
            cur = w
        cursor += len(w) + 1
        if cur == w and not lines:
            cur_start = cursor - len(w) - 1
    if cur:
        lines.append((cur, cur_start, cur_start + len(cur)))
    # recompute offsets robustly
    fixed, pos = [], 0
    for line, _s, _e in lines:
        idx = norm.find(line, pos)
        if idx < 0:
            idx = pos
        fixed.append((line, idx, idx + len(line)))
        pos = idx + len(line)
    return fixed, norm


def build_text_stack(blocks, brand, anchor_y: int) -> TextStack:
    """The headline block is serif and sets in two tones - line one cream, the rest
    accent - unless the block carries an explicit highlight, in which case the
    highlight wins and the whole headline stays cream. One accent gesture per frame."""
    lay = brand["layout"]
    scale = brand["type_scale"]
    fonts = brand["fonts"]
    hcfg = brand.get("headline", {})
    x = lay["margin_x"]
    max_w = lay["max_text_width"]

    stack = TextStack(top=anchor_y, bottom=anchor_y)
    y = anchor_y

    for bi, blk in enumerate(blocks):
        size_key = blk.get("size") or ("big" if bi == 0 else "med")
        size = scale.get(size_key, scale["med"])
        is_headline = size_key == "big"
        if is_headline:
            font_key = hcfg.get("font", "serif_bold")
        else:
            font_key = "sans"
        font_path = fonts.get(font_key, fonts["sans"])
        font = get_font(font_path, size)

        lines, norm = wrap_with_offsets(blk.get("text") or "", font, max_w)

        hl = (blk.get("highlights") or [None])[0]
        hl_range = None
        hl_style = ""
        if hl and hl.get("text"):
            htxt = " ".join(str(hl["text"]).split())
            idx = norm.find(htxt)
            if idx >= 0:
                hl_range = (idx, idx + len(htxt))
                hl_style = hl.get("style") or "underline"

        two_tone = bool(hcfg.get("two_tone", True)) and is_headline and not hl_range
        lh = float(hcfg.get("line_height", 1.06)) if is_headline else 1.22
        line_h = int(size * lh)

        # Two-tone splits the headline down the middle rather than after line one.
        # After line one is what the mockup shows, but that mockup headline is two
        # lines; on a four-line headline the same rule leaves one cream line against
        # three accent ones, which reads as a mistake rather than a device.
        split = (len(lines) + 1) // 2 if two_tone else 0

        for li, (line, s, e) in enumerate(lines):
            item = LineItem(text=line, x=x, y=y, font_path=font_path, font_size=size)
            if two_tone and li >= split:
                item.tone = "accent"
            if hl_range:
                hs, he = hl_range
                ov_s, ov_e = max(hs, s), min(he, e)
                if ov_s < ov_e:
                    item.hl_start = ov_s - s
                    item.hl_end = ov_e - s
                    item.hl_style = hl_style
            stack.items.append(item)
            y += line_h + lay["line_gap"]

        y += lay["block_gap"]

    stack.bottom = y - lay["block_gap"]
    return stack


def draw_stack(img: Image.Image, stack: TextStack, brand: dict, dim: bool):
    """Dimmed continuation text drops highlights and the two-tone treatment and
    drops to low opacity, at pixel-identical positions."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    colors = brand["colors"]
    accent = rgba(colors["accent"])
    hlcfg = brand["highlight"]

    for it in stack.items:
        font = it.font
        base_col = rgba(colors["text_dim"]) if dim else (
            accent if it.tone == "accent" else rgba(colors["text"]))

        if dim or it.hl_start < 0:
            d.text((it.x, it.y), it.text, font=font, fill=base_col)
            continue

        pre = it.text[:it.hl_start]
        mid = it.text[it.hl_start:it.hl_end]
        pre_w = measure(pre, font)[0] if pre else 0
        mid_w = measure(mid, font)[0]

        d.text((it.x, it.y), it.text, font=font, fill=base_col)
        if it.hl_style == "text":
            d.text((it.x + pre_w, it.y), mid, font=font, fill=accent)
        elif it.hl_style == "underline":
            y0 = it.y + it.font_size + hlcfg["offset_below_baseline"]
            d.rounded_rectangle(
                [it.x + pre_w, y0, it.x + pre_w + mid_w, y0 + hlcfg["thickness"]],
                radius=hlcfg["radius"], fill=accent,
            )
        elif it.hl_style == "strike":
            y0 = it.y + int(it.font_size * 0.58)
            d.rounded_rectangle(
                [it.x + pre_w, y0, it.x + pre_w + mid_w, y0 + hlcfg["thickness"]],
                radius=hlcfg["radius"], fill=accent,
            )

    img.alpha_composite(layer)


# --------------------------------------------------------------------------
# the field: the only background there is
# --------------------------------------------------------------------------

_FIELD_CACHE: dict[str, Image.Image] = {}


def _sparkle(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill):
    """The four-point star in the S45 lockup. Concave diamond, drawn as a polygon
    so it scales with the mark rather than living in a bitmap."""
    w = r * 0.30
    d.polygon(
        [(cx, cy - r), (cx + w, cy - w), (cx + r, cy), (cx + w, cy + w),
         (cx, cy + r), (cx - w, cy + w), (cx - r, cy), (cx - w, cy - w)],
        fill=fill,
    )


def field_background(brand: dict, chrome: bool = True) -> Image.Image:
    """Deep teal, graph-paper grid, corner vignette, fine grain, the S45 lockup and
    the kicker pill. Deterministic, so it is built once and copied.

    `chrome=False` gives the same field without the mark and kicker - for
    continuation frames, which inherit the chrome already drawn on the frame that
    opened the chain."""
    f = brand["field"]
    colors = brand["colors"]
    key = repr((brand["canvas"], f, colors["field_base"], colors["field_deep"],
                colors["grid_line"], colors["accent"], colors["text"], chrome))
    if key in _FIELD_CACHE:
        return _FIELD_CACHE[key].copy()

    w = brand["canvas"]["width"]
    h = brand["canvas"]["height"]

    base = Image.new("RGBA", (w, h), rgba(colors["field_base"]))

    # -- graph paper -----------------------------------------------------
    spacing = int(f.get("grid_spacing", 60))
    if spacing > 0:
        grid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grid)
        gcol = rgba(colors["grid_line"])
        gw = int(f.get("grid_width", 1))
        for x in range(0, w + 1, spacing):
            gd.line([(x, 0), (x, h)], fill=gcol, width=gw)
        for y in range(0, h + 1, spacing):
            gd.line([(0, y), (w, y)], fill=gcol, width=gw)
        base.alpha_composite(grid)

    # -- vignette: the deeper teal creeping in from the edges ------------
    vop = int(f.get("vignette_opacity", 90))
    if vop > 0:
        feather = max(1, int(f.get("vignette_feather", 620)))
        mask = Image.new("L", (w, h), 0)
        md = ImageDraw.Draw(mask)
        md.rectangle([0, 0, w, h], fill=vop)
        md.rounded_rectangle([feather // 3, feather // 3, w - feather // 3,
                              h - feather // 3], radius=feather // 2, fill=0)
        mask = mask.filter(ImageFilter.GaussianBlur(feather // 4))
        shade = Image.new("RGBA", (w, h), rgba(colors["field_deep"], 255))
        shade.putalpha(mask)
        base.alpha_composite(shade)

    # -- fine deterministic grain ----------------------------------------
    gop = int(f.get("grain_opacity", 7))
    if gop > 0:
        rnd = random.Random(int(f.get("grain_seed", 45)))
        sw, sh = w // 2, h // 2
        noise = Image.frombytes("L", (sw, sh), rnd.randbytes(sw * sh))
        noise = noise.resize((w, h), Image.NEAREST)
        grain = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        grain.putalpha(noise.point(lambda v: int(v * gop / 255)))
        base.alpha_composite(grain)

    # The chrome goes on its own layer and is composited. Drawing a part-alpha fill
    # straight onto an RGBA image *sets* the alpha instead of blending it, so the
    # "dimmed" mark would come out at full strength - which is exactly the sort of
    # thing that only shows up as a footer louder than the headline.
    chrome_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(chrome_layer)

    if chrome:
        # -- S45 lockup, top left ----------------------------------------
        msize = int(f.get("mark_size", 54))
        mfont = get_font(brand["fonts"]["sans_bold"], msize)
        mx, my = f.get("mark_x", 84), f.get("mark_y", 250)
        cream = rgba(colors["text"], int(f.get("mark_opacity", 255)))
        if f.get("mark_sparkle", True):
            r = msize * 0.40
            _sparkle(d, mx + r, my + msize * 0.52, r, cream)
            mx = int(mx + r * 2 + msize * 0.28)
        d.text((mx, my), f.get("mark_text", "S45"), font=mfont, fill=cream)

        # -- kicker pill, top right --------------------------------------
        ktext = f.get("kicker_text") or ""
        if ktext:
            kfont = brand_font(brand, "mono", "kicker")
            pad_x = int(f.get("kicker_pad_x", 22))
            pad_y = int(f.get("kicker_pad_y", 14))
            kw = measure(ktext, kfont)[0]
            kh = int(kfont.size * 1.15)
            x1 = int(f.get("kicker_x", w - 84))
            x0 = x1 - kw - 2 * pad_x
            y0 = int(f.get("kicker_y", 250))
            y1 = y0 + kh + 2 * pad_y
            d.rounded_rectangle([x0, y0, x1, y1], radius=8,
                                outline=rgba(colors["card_rule"]), width=2)
            d.text((x0 + pad_x, y0 + pad_y), ktext, font=kfont,
                   fill=rgba(colors["accent"]))

    # -- footer hairline + small mark ------------------------------------
    inset = int(f.get("rule_inset", 84))
    d.line([(inset, f["rule_y"]), (w - inset, f["rule_y"])],
           fill=rgba(colors["field_rule"]), width=1)

    fm = f.get("footer_mark_text")
    if fm:
        ffont = get_font(brand["fonts"]["sans_bold"], int(f.get("footer_mark_size", 28)))
        d.text((f.get("footer_mark_x", 84), f.get("footer_mark_y", 1856)), fm,
               font=ffont, fill=rgba(colors["text"], int(f.get("footer_mark_opacity", 120))))

    base.alpha_composite(chrome_layer)

    _FIELD_CACHE[key] = base
    return base.copy()


def chrome_bottom(brand: dict) -> int:
    """Where the drawn chrome stops and content may start."""
    f = brand["field"]
    return int(f.get("mark_y", 250)) + int(f.get("mark_size", 54)) + 46


# --------------------------------------------------------------------------
# note components: eyebrow, metric cards, bullet list, signal box
# --------------------------------------------------------------------------

def draw_eyebrow(img: Image.Image, brand: dict, text: str, y: int) -> int:
    cfg = brand.get("eyebrow", {})
    font = brand_font(brand, "mono", cfg.get("size_key", "kicker"))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    draw_tracked(d, (brand["layout"]["margin_x"], y), text.upper(), font,
                 rgba(brand["colors"]["text"], 200), int(cfg.get("tracking", 3)))
    img.alpha_composite(layer)
    return y + int(font.size * 1.25) + int(cfg.get("gap_below", 26))


def _delta_color(brand: dict, direction: str):
    c = brand["colors"]
    return {
        "up": rgba(c["positive"]),
        "down": rgba(c["negative"]),
    }.get(str(direction or "flat"), rgba(c["neutral"]))


def draw_metric_cards(img: Image.Image, brand: dict, metrics: list, y: int) -> int:
    """The three-up row. One panel, hairline dividers, mono values. Deltas take
    their colour from an explicit `direction` in the config - never from parsing a
    leading minus sign, because '-0.0% WoW' on a fall and a rise look identical to a
    regex and completely different to a reader."""
    cfg = brand["metric_cards"]
    colors = brand["colors"]
    lay = brand["layout"]
    metrics = list(metrics)[:int(cfg.get("max_cards", 3))]
    if not metrics:
        return y

    y += int(cfg.get("gap_above", 44))
    x0 = lay["margin_x"]
    x1 = brand["canvas"]["width"] - lay["margin_x"]
    h = int(cfg.get("height", 176))

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x0, y, x1, y + h], radius=int(cfg.get("corner_radius", 10)),
                        fill=rgba(colors["card_fill"]))

    n = len(metrics)
    cell_w = (x1 - x0) / n
    label_font = brand_font(brand, "mono", "metric_label")
    value_font = get_font(brand["fonts"][cfg.get("value_font", "mono_bold")],
                          brand["type_scale"]["metric_value"])
    delta_font = brand_font(brand, "sans_bold", "metric_delta")
    tracking = int(cfg.get("label_tracking", 2))

    for i, m in enumerate(metrics):
        cx0 = x0 + cell_w * i
        cx_mid = cx0 + cell_w / 2

        if cfg.get("divider", True) and i:
            d.line([(cx0, y + 22), (cx0, y + h - 22)],
                   fill=rgba(colors["field_rule"]), width=1)

        label = str(m.get("label") or "").upper()
        value = str(m.get("value") or "")
        delta = str(m.get("delta") or "")

        ly = y + int(cfg.get("pad_y", 22))
        lw = tracked_width(label, label_font, tracking)
        draw_tracked(d, (cx_mid - lw / 2, ly), label, label_font,
                     rgba(colors["accent"], 210), tracking)

        vy = ly + int(label_font.size * 1.9)
        vw = measure(value, value_font)[0]
        d.text((cx_mid - vw / 2, vy), value, font=value_font, fill=rgba(colors["text"]))

        if delta:
            dy = vy + int(value_font.size * 1.35)
            dw = measure(delta, delta_font)[0]
            d.text((cx_mid - dw / 2, dy), delta, font=delta_font,
                   fill=_delta_color(brand, m.get("direction")))

    img.alpha_composite(layer)
    return y + h + int(cfg.get("gap_below", 52))


def draw_bullet_list(img: Image.Image, brand: dict, rows: list, y: int,
                     label: str | None = None) -> int:
    """'WHAT CHANGED:' and its dotted spine. Rows wrap; the dot always sits on the
    first line of its row, and the connector runs dot to dot, not edge to edge."""
    cfg = brand["bullet_list"]
    colors = brand["colors"]
    rows = [str(r) for r in rows if str(r).strip()][:int(cfg.get("max_rows", 8))]
    if not rows:
        return y

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    label_text = (label if label is not None else cfg.get("label_text", "")) or ""
    if label_text:
        lfont = brand_font(brand, "mono_bold", "label")
        draw_tracked(d, (brand["layout"]["margin_x"], y), label_text.upper(), lfont,
                     rgba(colors["accent"]), int(cfg.get("label_tracking", 4)))
        y += int(lfont.size * 1.3) + int(cfg.get("gap_below_label", 30))

    font = brand_font(brand, "sans", "bullet")
    text_x = int(cfg.get("text_x", 148))
    dot_x = int(cfg.get("dot_x", 100))
    dot_r = int(cfg.get("dot_radius", 12))
    max_w = brand["canvas"]["width"] - brand["layout"]["margin_x"] - text_x
    line_h = int(font.size * 1.28)

    dot_centres = []
    cursor = y
    for row in rows:
        lines, _ = wrap_with_offsets(row, font, max_w)
        cy = cursor + line_h // 2
        dot_centres.append(cy)
        for ln, _s, _e in lines:
            d.text((text_x, cursor), ln, font=font, fill=rgba(colors["text"]))
            cursor += line_h
        cursor += int(cfg.get("row_gap", 26))

    # the dashed spine, drawn under the dots
    if cfg.get("connector", True) and len(dot_centres) > 1:
        on, off = cfg.get("connector_dash", [6, 10])
        yy = dot_centres[0] + dot_r
        end = dot_centres[-1] - dot_r
        while yy < end:
            d.line([(dot_x, yy), (dot_x, min(yy + on, end))],
                   fill=rgba(colors["accent"], 120), width=2)
            yy += on + off

    for cy in dot_centres:
        d.ellipse([dot_x - dot_r, cy - dot_r, dot_x + dot_r, cy + dot_r],
                  fill=rgba(colors["accent"]))

    img.alpha_composite(layer)
    return cursor


def draw_signal_box(img: Image.Image, brand: dict, text: str, y: int) -> int:
    """The bordered callout. One idea, at most three lines - if it needs four it is
    an argument, not a signal, and belongs in a frame of its own."""
    cfg = brand["signal_box"]
    colors = brand["colors"]
    lay = brand["layout"]
    text = " ".join(str(text or "").split())
    if not text:
        return y

    y += int(cfg.get("gap_above", 44))
    x0 = lay["margin_x"]
    x1 = brand["canvas"]["width"] - lay["margin_x"]
    pad_x = int(cfg.get("pad_x", 34))
    pad_y = int(cfg.get("pad_y", 30))
    icon_r = int(cfg.get("icon_radius", 26))
    icon_gap = int(cfg.get("icon_gap", 24))
    rule_gap = int(cfg.get("rule_gap", 26))

    label = cfg.get("label", "Signal:")
    lfont = brand_font(brand, "sans", "signal_label")
    tfont = brand_font(brand, "sans", "signal")
    label_w = measure(label, lfont)[0]

    text_x = x0 + pad_x + icon_r * 2 + icon_gap + label_w + rule_gap * 2
    lines, _ = wrap_with_offsets(text, tfont, x1 - pad_x - text_x)
    lines = lines[:int(cfg.get("max_lines", 3))]
    line_h = int(tfont.size * 1.32)
    box_h = max(icon_r * 2, len(lines) * line_h) + 2 * pad_y

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x0, y, x1, y + box_h], radius=int(cfg.get("border_radius", 12)),
                        outline=rgba(colors["accent"], 190),
                        width=int(cfg.get("border_width", 2)))

    mid = y + box_h // 2
    icx = x0 + pad_x + icon_r
    d.ellipse([icx - icon_r, mid - icon_r, icx + icon_r, mid + icon_r],
              outline=rgba(colors["accent"], 200), width=2)
    ifont = brand_font(brand, "sans_bold", "signal_label")
    iw, ih = measure("!", ifont)
    d.text((icx - iw / 2, mid - ifont.size * 0.62), "!", font=ifont,
           fill=rgba(colors["accent"]))

    lx = icx + icon_r + icon_gap
    d.text((lx, mid - lfont.size * 0.62), label, font=lfont,
           fill=rgba(colors["text"], 200))

    rule_x = lx + label_w + rule_gap
    d.line([(rule_x, y + pad_y), (rule_x, y + box_h - pad_y)],
           fill=rgba(colors["field_rule"]), width=1)

    ty = y + (box_h - len(lines) * line_h) // 2
    for ln, _s, _e in lines:
        d.text((text_x, ty), ln, font=tfont, fill=rgba(colors["text"]))
        ty += line_h

    img.alpha_composite(layer)
    return y + box_h


# --------------------------------------------------------------------------
# charts
# --------------------------------------------------------------------------

def _nice_step(rough: float) -> float:
    """Round a step up to 1, 2, 2.5 or 5 times a power of ten. An axis reading
    20.2 / 15.1 / 10.1 / 5.0 is arithmetically correct and unreadable; 20 / 15 / 10
    / 5 is what a reader can hold in their head while looking at the bars."""
    if rough <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(rough))
    for mult in (1, 2, 2.5, 5, 10):
        if rough <= mult * mag:
            return mult * mag
    return 10 * mag


def _nice_bounds(values: list[float], zero_line: bool, steps: int) -> tuple[float, float, float]:
    """Returns (lo, hi, step), all snapped to the step so every gridline lands on a
    round number."""
    lo, hi = min(values), max(values)
    if zero_line:
        lo = min(lo, 0.0)
        hi = max(hi, 0.0)
    if hi == lo:
        hi = lo + (abs(lo) or 1.0)

    step = _nice_step((hi - lo) / max(1, steps))
    lo = math.floor(lo / step) * step
    hi = math.ceil(hi / step) * step
    # keep a little air above the tallest bar so its value label has somewhere to go
    if abs(hi - max(values)) < step * 0.35:
        hi += step
    return lo, hi, step


def _fmt(v: float, unit: str = "") -> str:
    if abs(v - round(v)) < 1e-9:
        s = f"{int(round(v)):,}"
    elif abs(v) >= 100:
        s = f"{v:,.0f}"
    else:
        s = f"{v:,.1f}"
    unit = str(unit or "").strip()
    if not unit:
        return s
    # a symbol closes up against the number, a word takes a space
    return f"{s}{unit}" if len(unit) == 1 else f"{s} {unit}"


def draw_chart(img: Image.Image, brand: dict, chart: dict, y: int) -> int:
    """Bar and line charts, drawn from `chart.series` in the config.

    Nothing here reaches the network. The numbers were written into the config by
    the generation step and reviewed by a human before approval, which is the only
    way a chart can carry the same audit trail as the sentence next to it."""
    cfg = brand["chart"]
    colors = brand["colors"]
    lay = brand["layout"]

    ctype = str(chart.get("type") or "bar")
    labels = [str(x) for x in (chart.get("labels") or [])]
    series = [s for s in (chart.get("series") or []) if s.get("values")]
    if not labels or not series:
        return y

    cap = int(cfg.get("max_points", 12))
    labels = labels[:cap]
    for s in series:
        s["values"] = list(s["values"])[:cap]

    y += int(cfg.get("gap_above", 40))
    x0 = lay["margin_x"]
    w = int(cfg.get("width", 912))
    h = int(cfg.get("height", 520))
    pl, pr = int(cfg.get("pad_left", 96)), int(cfg.get("pad_right", 24))
    pt, pb = int(cfg.get("pad_top", 64)), int(cfg.get("pad_bottom", 76))

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    d.rounded_rectangle([x0, y, x0 + w, y + h], radius=10,
                        fill=rgba(colors["card_fill"]))

    title = chart.get("title")
    unit = str(chart.get("unit") or "")
    if title:
        tfont = brand_font(brand, "mono_bold", "chart_title")
        draw_tracked(d, (x0 + 26, y + 20), str(title).upper(), tfont,
                     rgba(colors["accent"]), 2)

    # a legend needs its own band, otherwise it lands on the x-axis labels
    legend_h = int(cfg.get("legend_height", 38)) if len(series) > 1 else 0

    plot_x0 = x0 + pl
    plot_x1 = x0 + w - pr
    plot_y0 = y + pt
    plot_y1 = y + h - pb - legend_h
    plot_h = plot_y1 - plot_y0
    plot_w = plot_x1 - plot_x0

    all_vals = [float(v) for s in series for v in s["values"]]
    steps = max(2, int(cfg.get("grid_lines", 4)))
    lo, hi, step = _nice_bounds(all_vals, bool(cfg.get("zero_line", True)), steps)
    span = hi - lo

    def vy(v: float) -> float:
        return plot_y1 - (float(v) - lo) / span * plot_h

    # -- horizontal guides + axis labels ---------------------------------
    afont = brand_font(brand, "mono", "chart_axis")
    ticks = int(round(span / step))
    for i in range(ticks + 1):
        gv = lo + step * i
        gy = vy(gv)
        d.line([(plot_x0, gy), (plot_x1, gy)], fill=rgba(colors["grid_line"], 40), width=1)
        lab = _fmt(gv, unit)
        lw = measure(lab, afont)[0]
        d.text((plot_x0 - 14 - lw, gy - afont.size * 0.7), lab, font=afont,
               fill=rgba(colors["text"], 150))

    if cfg.get("zero_line", True) and lo < 0 < hi:
        zy = vy(0)
        d.line([(plot_x0, zy), (plot_x1, zy)], fill=rgba(colors["text"], 110), width=2)

    pal = cfg.get("series_colors", [[166, 200, 72]])

    def scol(i: int, s: dict):
        idx = s.get("color_index")
        idx = i if idx is None else int(idx)
        return rgba(pal[idx % len(pal)])

    n = len(labels)
    slot = plot_w / max(1, n)
    vfont = brand_font(brand, "mono", "chart_value")
    show_values = bool(cfg.get("value_labels", True)) and n <= 8

    if ctype == "bar":
        gap = float(cfg.get("bar_gap_ratio", 0.34))
        group_w = slot * (1 - gap)
        bar_w = min(group_w / len(series), float(cfg.get("bar_max_width", 110)))
        for si, s in enumerate(series):
            col = scol(si, s)
            for i, v in enumerate(s["values"]):
                if i >= n:
                    break
                cx = plot_x0 + slot * i + slot / 2
                bx0 = cx - (bar_w * len(series)) / 2 + bar_w * si
                top, bottom = vy(float(v)), vy(max(lo, 0.0) if lo < 0 else lo)
                if top > bottom:
                    top, bottom = bottom, top
                d.rounded_rectangle([bx0, top, bx0 + bar_w - 2, bottom],
                                    radius=int(cfg.get("bar_radius", 6)), fill=col)
                if show_values and len(series) == 1:
                    lab = _fmt(float(v), unit)
                    lw = measure(lab, vfont)[0]
                    d.text((bx0 + bar_w / 2 - lw / 2, top - vfont.size * 1.6), lab,
                           font=vfont, fill=rgba(colors["text"], 200))
    else:  # line
        lw_px = int(cfg.get("line_width", 5))
        pr_px = int(cfg.get("point_radius", 9))
        for si, s in enumerate(series):
            col = scol(si, s)
            pts = [(plot_x0 + slot * i + slot / 2, vy(float(v)))
                   for i, v in enumerate(s["values"][:n])]
            if len(pts) > 1:
                d.line(pts, fill=col, width=lw_px, joint="curve")
            for pi, (px, py) in enumerate(pts):
                d.ellipse([px - pr_px, py - pr_px, px + pr_px, py + pr_px], fill=col)
                if show_values and len(series) == 1:
                    lab = _fmt(float(s["values"][pi]), unit)
                    lwd = measure(lab, vfont)[0]
                    d.text((px - lwd / 2, py - pr_px - vfont.size * 1.7), lab,
                           font=vfont, fill=rgba(colors["text"], 200))

    # -- x labels ---------------------------------------------------------
    for i, lab in enumerate(labels):
        cx = plot_x0 + slot * i + slot / 2
        lw = measure(lab, afont)[0]
        d.text((cx - lw / 2, plot_y1 + 16), lab, font=afont,
               fill=rgba(colors["text"], 175))

    # -- legend, only when there is something to disambiguate -------------
    if len(series) > 1:
        lx = plot_x0
        ly = y + h - legend_h + 2
        for si, s in enumerate(series):
            name = str(s.get("name") or f"series {si + 1}")
            d.rectangle([lx, ly + 6, lx + 22, ly + 18], fill=scol(si, s))
            d.text((lx + 32, ly), name, font=afont, fill=rgba(colors["text"], 190))
            lx += 32 + measure(name, afont)[0] + 40

    img.alpha_composite(layer)
    return y + h + int(cfg.get("gap_below", 34))


# --------------------------------------------------------------------------
# fixed furniture: identity block, source line, disclosure, artifact
# --------------------------------------------------------------------------

def draw_identity_block(img: Image.Image, brand: dict, policy: dict):
    """Frame 1 only. Fixed position, size and contrast from brand.json.
    Not configurable per sequence. That is deliberate."""
    ib = brand["identity_block"]
    lines = core.identity_block_lines(policy)
    if not lines:
        raise RuntimeError("identity block has no content - refusing to render frame 1")

    font = brand_font(brand, "sans", ib.get("size_key", "identity"))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    x, y = ib["x"], ib["y"]
    widths = [measure(ln, font)[0] for ln in lines]
    line_h = int(font.size * 1.3)
    pad = ib.get("plate_padding", 20)
    box_w = max(widths) + 2 * pad
    box_h = line_h * len(lines) + 2 * pad - int(font.size * 0.3)

    if ib.get("plate", True):
        d.rounded_rectangle(
            [x - pad, y - pad, x - pad + box_w, y - pad + box_h],
            radius=8, fill=rgba(brand["colors"]["field_deep"],
                                int(ib.get("plate_opacity", 150))),
        )

    col = rgba(brand["colors"]["identity"])
    for i, ln in enumerate(lines):
        d.text((x, y + i * line_h), ln, font=font, fill=col)
    img.alpha_composite(layer)


def draw_source_line(img: Image.Image, brand: dict, text: str, y: int) -> int:
    font = brand_font(brand, "sans", "source")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lines, _ = wrap_with_offsets(text, font, brand["layout"]["max_text_width"])
    for ln, _s, _e in lines:
        d.text((brand["layout"]["margin_x"], y), ln, font=font,
               fill=rgba(brand["colors"]["source"]))
        y += int(font.size * 1.4)
    img.alpha_composite(layer)
    return y


def draw_footer(img: Image.Image, brand: dict, disclosure: str, sources: str | None):
    """The two-column footer under the hairline: DISCLOSURE on the left, DATA
    SOURCES on the right. Fixed position, size and contrast, not per-sequence
    configurable. Never at a size or contrast that reads as hidden."""
    dcfg = brand["disclosure"]
    colors = brand["colors"]
    lay = brand["layout"]

    body = brand_font(brand, "sans", dcfg.get("size_key", "disclosure"))
    label_font = brand_font(brand, "mono_bold", dcfg.get("label_size_key", "metric_label"))

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    x0 = dcfg["x"]
    full_w = brand["canvas"]["width"] - 2 * lay["margin_x"]
    gap = int(dcfg.get("column_gap", 40))
    two_col = bool(sources)
    col_w = (full_w - gap) // 2 if two_col else full_w

    def column(x: int, label: str, text: str, width: int):
        yy = dcfg["y"]
        draw_tracked(d, (x, yy), label, label_font, rgba(colors["accent"], 200), 2)
        yy += int(label_font.size * 1.6)
        lines, _ = wrap_with_offsets(text, body, width)
        for ln, _s, _e in lines:
            d.text((x, yy), ln, font=body, fill=rgba(colors["disclosure"]))
            yy += int(body.size * 1.3)

    column(x0, dcfg.get("disclosure_label", "DISCLOSURE"), disclosure, col_w)
    if two_col:
        column(x0 + col_w + gap, dcfg.get("sources_label", "DATA SOURCES"),
               sources, col_w)

    img.alpha_composite(layer)


def draw_artifact(img: Image.Image, brand: dict, path: Path, pos: str,
                  band_top: int, band_bottom: int):
    """Composite as a rounded card with a soft shadow, inside the band left over
    below the text. Cap upscaling. Keep text clear of the card."""
    cfg = brand["artifact_card"]
    try:
        card = Image.open(path).convert("RGBA")
    except OSError:
        return

    band_h = max(0, band_bottom - band_top)
    if band_h < 160:
        return

    max_w = cfg["max_width"]
    scale = min(max_w / card.width, float(cfg.get("max_upscale", 1.4)))
    card = card.resize((max(1, int(card.width * scale)), max(1, int(card.height * scale))),
                       Image.LANCZOS)

    # a tall page crops at the bottom and reads as a page peeking in
    if card.height > band_h:
        card = card.crop((0, 0, card.width, band_h))

    r = cfg.get("corner_radius", 22)
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, card.width - 1, card.height - 1],
                                          radius=r, fill=255)
    card.putalpha(mask)

    x = (img.width - card.width) // 2
    if pos == "upper":
        y = band_top
    elif pos == "center":
        y = band_top + (band_h - card.height) // 2
    else:
        y = band_bottom - card.height

    blur = cfg.get("shadow_blur", 26)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([x + 6, y + 10, x + card.width + 6, y + card.height + 10],
                         radius=r, fill=(0, 0, 0, int(cfg.get("shadow_opacity", 150))))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)))
    img.alpha_composite(card, (x, y))


# --------------------------------------------------------------------------
# the render
# --------------------------------------------------------------------------

class RenderError(RuntimeError):
    pass


def anchor_for(position: str, brand: dict) -> int:
    lay = brand["layout"]
    return {
        "top": lay["top_anchor_y"],
        "center": lay["center_anchor_y"],
        "bottom": lay["bottom_anchor_y"],
    }.get(position or "top", lay["top_anchor_y"])


def render_sequence(slug: str, only_frame: int | None = None,
                    policy: dict | None = None, brand: dict | None = None,
                    skip_validation: bool = False) -> dict:
    policy = policy or core.load_policy()
    brand = brand or core.load_brand()
    seq_dir = core.sequence_dir(slug)
    cfg = core.load_config(slug)

    warnings: list[str] = []

    # -- hard stop: the identity block never degrades --------------------
    ok, why = core.policy_registration_ready(policy)
    if not ok:
        raise RenderError(
            "REFUSING TO RENDER. identity_block_hard_stop: " + why
        )

    if not skip_validation:
        issues = validate.validate_config(cfg, slug, policy)
        errs = validate.errors(issues)
        if errs:
            raise RenderError(
                "REFUSING TO RENDER. validation failed:\n"
                + validate.format_issues(errs, slug)
            )
        warnings += [f'[{i["rule"]}] {i["where"]}: {i["message"]}'
                     for i in validate.warnings(issues)]

    W = brand["canvas"]["width"]
    frames = cfg.get("frames") or []
    floor_y = brand["field"]["rule_y"] - 40

    # --frame N re-renders N plus its continuations, nothing else
    if only_frame is None:
        write_set = {int(f["n"]) for f in frames}
    else:
        write_set = set()
        take = False
        for f in frames:
            n = int(f["n"])
            if n == int(only_frame):
                take = True
            elif take and not f.get("continues"):
                break
            if take:
                write_set.add(n)

    chain_bg: Image.Image | None = None
    chain_stacks: list[TextStack] = []
    chain_anchor = anchor_for("top", brand)

    written: list[str] = []

    for fr in frames:
        n = int(fr["n"])
        continues = bool(fr.get("continues"))

        # -- background: always the drawn field ---------------------------
        if continues and chain_bg is not None:
            base = chain_bg.copy()
        else:
            bg = fr.get("background") or {"type": "field"}
            btype = bg.get("type") or "field"
            # "note" is the full capital-markets-note chrome - lockup and kicker.
            # "field" is the quiet version: lockup only, nothing announcing itself.
            base = field_background(brand, chrome=bool(bg.get("chrome", btype == "note")))
            chain_bg = base.copy()
            chain_stacks = []
            chain_anchor = anchor_for(fr.get("text_position"), brand)

        img = base

        # -- where content may start --------------------------------------
        start_y = chain_anchor
        if chain_stacks:
            start_y = chain_stacks[-1].bottom + brand["layout"]["block_gap"] + 8
        else:
            start_y = max(start_y, chrome_bottom(brand))
            if n == 1 and policy.get("identity_block_required"):
                start_y = max(start_y, brand["identity_block"].get("reserve_band_to_y", 264))

        # -- eyebrow ------------------------------------------------------
        eyebrow = fr.get("eyebrow") if not continues else None
        if eyebrow:
            start_y = draw_eyebrow(img, brand, str(eyebrow), start_y)

        # -- text stack ---------------------------------------------------
        stack = build_text_stack(fr.get("blocks") or [], brand, start_y)
        for s in chain_stacks:
            draw_stack(img, s, brand, dim=True)
        draw_stack(img, stack, brand, dim=False)
        cursor = stack.bottom

        # -- note components, in a fixed order ----------------------------
        if fr.get("metrics"):
            cursor = draw_metric_cards(img, brand, fr["metrics"], cursor)
        if fr.get("chart"):
            cursor = draw_chart(img, brand, fr["chart"], cursor)
        if fr.get("bullets"):
            cursor = draw_bullet_list(img, brand, fr["bullets"], cursor,
                                      fr.get("bullets_label"))
        if fr.get("signal"):
            cursor = draw_signal_box(img, brand, fr["signal"], cursor)

        # -- source line, artifact, footer --------------------------------
        # Where the source goes depends on what it is sourcing. Under a sentence it
        # sits directly beneath the claim, because proximity is what makes a reader
        # connect the two. Under a chart or a metric row the claim *is* the panel,
        # and the source belongs in the footer's DATA SOURCES column where it does
        # not compete with the numbers.
        src_line = fr.get("source_line")
        chart_src = (fr.get("chart") or {}).get("source")
        if chart_src and not src_line:
            src_line = chart_src

        has_panel = bool(fr.get("chart") or fr.get("metrics") or fr.get("bullets")
                         or fr.get("signal"))
        data_sources = fr.get("data_sources")
        if src_line and has_panel and not data_sources:
            data_sources = src_line
        elif src_line and not has_panel:
            cursor = draw_source_line(img, brand, src_line, cursor + 24)

        art_name = fr.get("artifact")
        if art_name:
            ap = core.resolve_artifact(art_name)
            if ap is None:
                warnings.append(f"frame {n}: artifact '{art_name}' not in assets/artifacts/ "
                                f"- skipped")
            else:
                draw_artifact(img, brand, ap, fr.get("artifact_pos") or "lower",
                              cursor + 40, floor_y)
                cursor = floor_y

        is_cta_frame = fr.get("role") == "cta"
        if src_line or is_cta_frame or data_sources:
            key = "cta" if is_cta_frame else "statistic"
            draw_footer(img, brand, policy["disclosure_lines"][key], data_sources)

        if cursor > floor_y:
            warnings.append(
                f"frame {n}: content runs to y={int(cursor)}, past the footer rule at "
                f"y={floor_y}. Cut a bullet, a metric or a line of the headline - the "
                f"renderer will not shrink type to make it fit.")

        if n == 1 and policy.get("identity_block_required"):
            draw_identity_block(img, brand, policy)

        chain_stacks = chain_stacks + [stack]

        # -- write -------------------------------------------------------
        if n in write_set:
            out = seq_dir / f"frame_{n}.png"
            img.convert("RGB").save(out, "PNG", compress_level=4)
            written.append(out.name)

    post_order = write_post_order(slug, cfg, policy)
    return {"slug": slug, "frames": written, "warnings": warnings,
            "post_order": str(post_order.relative_to(core.ROOT))}


# --------------------------------------------------------------------------
# post-order.md
# --------------------------------------------------------------------------

def write_post_order(slug: str, cfg: dict, policy: dict) -> Path:
    seq_dir = core.sequence_dir(slug)
    hand = core.hand_post_frames(cfg)
    approved = core.approval_path(slug).exists()

    L = []
    L.append(f"# Post order - {slug}")
    L.append("")
    L.append(f"- Type: `{cfg.get('type')}`")
    L.append(f"- Highlight: **{cfg.get('highlight_title') or '(none)'}**")
    L.append(f"- Handle: {cfg.get('profile', {}).get('handle', '@s45')}")
    L.append(f"- Frames: {len(cfg.get('frames', []))}")
    L.append("")

    if not approved:
        L.append("> **THIS SEQUENCE IS UNAPPROVED.** It is not publishable until")
        L.append("> `approval.json` exists, carrying an approver from `policy.approvers`,")
        L.append("> a timestamp, and the SHA-256 of every frame PNG. `schedule.py` will")
        L.append("> refuse it. Claude never writes `approval.json`.")
    else:
        L.append("> Approval on file. `schedule.py` recomputes frame hashes before pushing;")
        L.append("> any frame changed after approval invalidates it.")
    L.append("")

    L.append("## Frames")
    L.append("")
    L.append("| # | Role | Components | Sticker | Post |")
    L.append("|---|---|---|---|---|")
    for fr in cfg.get("frames", []):
        n = fr.get("n")
        parts = []
        if fr.get("continues"):
            parts.append("continues previous")
        if fr.get("metrics"):
            parts.append(f"{len(fr['metrics'])} metrics")
        if fr.get("chart"):
            parts.append(f"{fr['chart'].get('type', 'bar')} chart")
        if fr.get("bullets"):
            parts.append(f"{len(fr['bullets'])} bullets")
        if fr.get("signal"):
            parts.append("signal")
        if fr.get("artifact"):
            parts.append(f"artifact `{fr['artifact']}`")
        comp = ", ".join(parts) if parts else "text only"
        st = fr.get("sticker")
        stdesc = "-"
        if st:
            stdesc = f"**{st.get('kind')}**: {st.get('text') or st.get('destination') or ''}"
        mode = "**hand-post**" if n in hand else "scheduled"
        L.append(f"| {n} | {fr.get('role')} | {comp} | {stdesc} | {mode} |")
    L.append("")

    charted = [fr.get("n") for fr in cfg.get("frames", []) if fr.get("chart")]
    if charted:
        L.append(f"**Charted frames: {', '.join(str(c) for c in charted)}.** Every value "
                 "plotted is written into `config.json` and rendered offline - check the "
                 "numbers against the named source before approving, because approval "
                 "covers the chart exactly as it covers the sentence beside it.")
        L.append("")

    if hand:
        L.append(f"**Hand-post-only frames: {', '.join(str(h) for h in hand)}.** "
                 "Auto-published stories have no native stickers, no tappable links, "
                 "no music. Three minutes in the app buys the link sticker that makes "
                 "the ask work at all.")
        L.append("")

    ask = cfg.get("ask")
    if ask:
        L.append("## Ask")
        L.append("")
        L.append(f"- Shape: `{ask.get('shape')}`")
        L.append(f"- Destination: `{ask.get('destination')}`")
        L.append(f"- Situation: {ask.get('situation')}")
        L.append(f"- Disclosure baked into the pixels: "
                 f"\"{policy['disclosure_lines']['cta']}\"")
        L.append("")

    L.append("## Compliance")
    L.append("")
    L.append(f"- Frame 1 carries the identity block: **yes** "
             f"({' / '.join(core.identity_block_lines(policy))})")
    L.append(f"- scope_attestation: `{cfg.get('scope_attestation')}`")
    L.append("- Push all frames as ONE story post carrying the images in order, never N "
             "separate posts. Separate posts publish out of order and a scrambled "
             "argument is worse than none.")
    L.append(f"- Save to Highlight: **{cfg.get('highlight_title') or '(set one)'}**")
    L.append("- Same content on WhatsApp broadcast? The identity block goes at the top "
             "there too. The circular reaches closed groups.")
    L.append("- Run `archive.py` immediately after publishing.")
    L.append("")

    out = seq_dir / "post-order.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return out
