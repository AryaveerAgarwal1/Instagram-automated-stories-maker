"""Validation. Every failure names the rule and quotes the offending span.

Nothing renders that breaks these. The renderer calls validate_config() first
and refuses on any error.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import core

SCOPE_ATTESTATION = "private_markets_only"

# A digit-bearing statistic. Bare years and frame-ish numbers are not statistics,
# but anything with a %, a magnitude word, a currency, or a multiplier is.
STAT_PATTERNS = [
    re.compile(r"\d+(\.\d+)?\s*%"),
    re.compile(r"(?<![A-Za-z])(?:Rs\.?|INR|₹|\$|€|£)\s*\d", re.IGNORECASE),
    re.compile(r"\b\d+(\.\d+)?\s*(x|times)\b", re.IGNORECASE),
    re.compile(r"\b\d+(\.\d+)?\s*(bn|mn|cr|crore|lakh|billion|million|thousand|k)\b", re.IGNORECASE),
    re.compile(r"\b\d+(\.\d+)?\s*(bps|basis points)\b", re.IGNORECASE),
    re.compile(r"\b(fell|rose|grew|declined|up|down)\b[^.]{0,40}\b\d", re.IGNORECASE),
    re.compile(r"\b\d+\s+(rounds|deals|companies|firms|founders|mandates)\b", re.IGNORECASE),
]

KEYWORD_ASK = re.compile(
    r"\b(reply|comment|dm|message)\b[^.]{0,30}\b(with|['\"’])", re.IGNORECASE
)

# A bare all-caps token is often a listed name the pattern list will not catch.
# Warning, not error: the pattern list is a floor, not a guarantee.
CAPS_TOKEN = re.compile(r"(?<![A-Za-z&])[A-Z]{4,}(?![A-Za-z&])")
CAPS_ALLOW = {
    "COGS", "SEBI", "SAAS", "ARPU", "EBITDA", "IPO", "IPOS", "NDAS", "LTV", "CAC",
    "TRUE", "FALSE", "OKRS", "KPIS", "GAAP", "IFRS", "ONLY", "THIS", "THAT", "WITH",
    "FROM", "WHAT", "WHEN", "MOST", "FREE", "INDIA", "AND", "THE",
}


class Issue(dict):
    """{'level','rule','where','message','span'}"""


def _issue(level, rule, where, message, span=None) -> Issue:
    return Issue(level=level, rule=rule, where=where, message=message, span=span or "")


def _err(rule, where, message, span=None):
    return _issue("error", rule, where, message, span)


def _warn(rule, where, message, span=None):
    return _issue("warning", rule, where, message, span)


# --------------------------------------------------------------------------
# text scans
# --------------------------------------------------------------------------

def scan_text(text: str, policy: dict, where: str) -> list[Issue]:
    """Listed-security / banned-term scan. A hit is a hard failure quoting the span."""
    issues: list[Issue] = []
    if not text:
        return issues

    low = text.lower()
    for term in policy.get("banned_terms", []):
        t = str(term).lower().strip()
        if not t:
            continue
        m = re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", low)
        if m:
            issues.append(_err(
                "banned_term", where,
                f'banned term "{term}"',
                text[max(0, m.start() - 24):m.end() + 24].strip(),
            ))

    for pat in policy.get("banned_patterns", []):
        try:
            rx = re.compile(pat)
        except re.error:
            issues.append(_warn("banned_pattern", "policy.json",
                                f"uncompilable pattern {pat!r}"))
            continue
        m = rx.search(text)
        if m:
            issues.append(_err(
                "listed_security_scan", where,
                f"matches banned pattern {pat}",
                m.group(0),
            ))

    for m in CAPS_TOKEN.finditer(text):
        tok = m.group(0)
        if tok in CAPS_ALLOW:
            continue
        issues.append(_warn(
            "possible_listed_name", where,
            f'"{tok}" reads like a company or ticker in caps. The pattern list is a '
            "floor, not a guarantee - check this is not a listed security before "
            "approving.", tok,
        ))
    return issues


def has_statistic(text: str) -> str | None:
    for rx in STAT_PATTERNS:
        m = rx.search(text or "")
        if m:
            return m.group(0)
    return None


# --------------------------------------------------------------------------
# note components
# --------------------------------------------------------------------------

MAX_METRIC_CARDS = 3
MAX_BULLET_ROWS = 8
MAX_BULLET_CHARS = 92
MAX_SIGNAL_CHARS = 190
MAX_CHART_POINTS = 12
MAX_CHART_SERIES = 4


def validate_metrics(metrics, policy: dict, where: str) -> list[Issue]:
    """The three-up row. `direction` is required and is not inferred, because the
    renderer colours the delta from it - green on a fall would be a factual error
    rendered in the house style."""
    issues: list[Issue] = []
    if metrics in (None, [], {}):
        return issues
    if not isinstance(metrics, list):
        issues.append(_err("metrics", where, "metrics must be a list of cards",
                           str(metrics)[:60]))
        return issues
    if len(metrics) > MAX_METRIC_CARDS:
        issues.append(_err("metric_count", where,
                           f"at most {MAX_METRIC_CARDS} metric cards - the row is "
                           "three-up and does not scroll", str(len(metrics))))
    for mi, m in enumerate(metrics):
        mw = f"{where} metric {mi + 1}"
        if not isinstance(m, dict):
            issues.append(_err("metric", mw, "each metric is an object", str(m)[:60]))
            continue
        if not str(m.get("label") or "").strip():
            issues.append(_err("metric_label", mw, "metric.label is required"))
        if not str(m.get("value") or "").strip():
            issues.append(_err("metric_value", mw, "metric.value is required"))
        if len(str(m.get("label") or "")) > 22:
            issues.append(_warn("metric_label_length", mw,
                                "a metric label is a caption, not a clause - it will be "
                                "cramped past ~22 characters", str(m.get("label"))))
        if len(str(m.get("value") or "")) > 14:
            issues.append(_warn("metric_value_length", mw,
                                "a metric value past ~14 characters will crowd its "
                                "neighbours", str(m.get("value"))))
        if m.get("delta"):
            d = m.get("direction")
            if d not in core.VALID_DELTA_DIRECTIONS:
                issues.append(_err(
                    "metric_direction", mw,
                    f"a metric carrying a delta must state direction, one of "
                    f"{sorted(core.VALID_DELTA_DIRECTIONS)}. The renderer colours the "
                    "delta from this field and will not guess it from a minus sign.",
                    str(d)))
        for k in ("label", "value", "delta"):
            issues += scan_text(str(m.get(k) or ""), policy, f"{mw} {k}")
    return issues


def validate_chart(chart, policy: dict, where: str) -> list[Issue]:
    """Charts are drawn from values in the config. Everything that could make a
    chart lie - mismatched label and value counts, an unlabelled axis, a series with
    no name in a multi-series plot - is an error here rather than a surprise on the
    rendered frame."""
    issues: list[Issue] = []
    if chart in (None, {}, []):
        return issues
    if not isinstance(chart, dict):
        issues.append(_err("chart", where, "chart must be an object", str(chart)[:60]))
        return issues

    ctype = chart.get("type")
    if ctype not in core.VALID_CHART_TYPES:
        issues.append(_err("chart_type", where,
                           f"chart.type must be one of {sorted(core.VALID_CHART_TYPES)}",
                           str(ctype)))

    labels = chart.get("labels")
    if not isinstance(labels, list) or not labels:
        issues.append(_err("chart_labels", where,
                           "chart.labels is required - an axis without labels is a "
                           "shape, not a chart", str(labels)[:60]))
        labels = []
    elif len(labels) > MAX_CHART_POINTS:
        issues.append(_err("chart_points", where,
                           f"at most {MAX_CHART_POINTS} points on a 1080px story frame",
                           str(len(labels))))

    series = chart.get("series")
    if not isinstance(series, list) or not series:
        issues.append(_err("chart_series", where, "chart.series is required",
                           str(series)[:60]))
        return issues
    if len(series) > MAX_CHART_SERIES:
        issues.append(_err("chart_series_count", where,
                           f"at most {MAX_CHART_SERIES} series - beyond that the legend "
                           "is doing the work the chart should", str(len(series))))

    for si, s in enumerate(series):
        sw = f"{where} series {si + 1}"
        if not isinstance(s, dict):
            issues.append(_err("chart_series", sw, "each series is an object", str(s)[:60]))
            continue
        vals = s.get("values")
        if not isinstance(vals, list) or not vals:
            issues.append(_err("chart_values", sw, "series.values is required",
                               str(vals)[:60]))
            continue
        bad = [v for v in vals if not isinstance(v, (int, float)) or isinstance(v, bool)]
        if bad:
            issues.append(_err("chart_values", sw,
                               "series.values must be numbers, not strings - the "
                               "renderer scales the axis from them", str(bad[:3])))
            continue
        if labels and len(vals) != len(labels):
            issues.append(_err(
                "chart_series_length", sw,
                f"series has {len(vals)} values against {len(labels)} labels. A chart "
                "whose points do not line up with its axis misstates the data.",
                f"{len(vals)} vs {len(labels)}"))
        if len(series) > 1 and not str(s.get("name") or "").strip():
            issues.append(_err("chart_series_name", sw,
                               "a multi-series chart needs a name on every series - the "
                               "legend is drawn from it"))
        issues += scan_text(str(s.get("name") or ""), policy, f"{sw} name")

    for lab in labels:
        issues += scan_text(str(lab), policy, f"{where} chart label")
    issues += scan_text(str(chart.get("title") or ""), policy, f"{where} chart title")
    issues += scan_text(str(chart.get("source") or ""), policy, f"{where} chart source")

    if not str(chart.get("title") or "").strip():
        issues.append(_warn("chart_title", where,
                            "an untitled chart makes the reader infer what is being "
                            "measured - give it a title"))
    if not str(chart.get("unit") or "").strip():
        issues.append(_warn("chart_unit", where,
                            "no unit on the axis. A bare number could be crore, percent "
                            "or count."))
    return issues


def validate_bullets(bullets, policy: dict, where: str) -> list[Issue]:
    issues: list[Issue] = []
    if bullets in (None, [], {}):
        return issues
    if not isinstance(bullets, list):
        issues.append(_err("bullets", where, "bullets must be a list of strings",
                           str(bullets)[:60]))
        return issues
    if len(bullets) > MAX_BULLET_ROWS:
        issues.append(_err("bullet_count", where,
                           f"at most {MAX_BULLET_ROWS} bullets on one frame",
                           str(len(bullets))))
    for bi, row in enumerate(bullets):
        bw = f"{where} bullet {bi + 1}"
        text = str(row or "").strip()
        if not text:
            issues.append(_err("bullet_text", bw, "bullet is empty"))
            continue
        if len(text) > MAX_BULLET_CHARS:
            issues.append(_warn("bullet_length", bw,
                                f"a bullet past {MAX_BULLET_CHARS} characters wraps to "
                                "three lines and stops scanning", text[:60]))
        issues += scan_text(text, policy, bw)
    return issues


def validate_signal(signal, policy: dict, where: str) -> list[Issue]:
    issues: list[Issue] = []
    if signal in (None, "", []):
        return issues
    if not isinstance(signal, str):
        issues.append(_err("signal", where, "signal must be a string", str(signal)[:60]))
        return issues
    text = signal.strip()
    if len(text) > MAX_SIGNAL_CHARS:
        issues.append(_err("signal_length", where,
                           f"the signal box holds three lines, about "
                           f"{MAX_SIGNAL_CHARS} characters. Longer than that is an "
                           "argument and belongs in its own frame.", text[:60]))
    issues += scan_text(text, policy, f"{where} signal")
    return issues


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def validate_config(cfg: dict, slug: str | None = None, policy: dict | None = None,
                    check_cooldown: bool = True) -> list[Issue]:
    policy = policy or core.load_policy()
    slug = slug or cfg.get("slug")
    issues: list[Issue] = []

    # -- 0. registration hard stop --------------------------------------
    ok, why = core.policy_registration_ready(policy)
    if not ok:
        issues.append(_err("identity_block_hard_stop", "config/policy.json", why))

    if str(policy.get("entity_status")) == "TBD_BY_COUNSEL":
        issues.append(_warn(
            "entity_status", "config/policy.json",
            "entity_status is still TBD_BY_COUNSEL. Q1 and Q2 at the top of the "
            "skill file must be answered by Indian counsel before the first post.",
        ))

    # -- 1. top level ----------------------------------------------------
    if not cfg.get("slug"):
        issues.append(_err("slug", "config", "slug is required"))
    elif not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(cfg["slug"])):
        issues.append(_err("slug", "config", "slug must be kebab-case", str(cfg["slug"])))

    ctype = cfg.get("type")
    if ctype not in core.VALID_TYPES:
        issues.append(_err("type", "config",
                           f"type must be one of {sorted(core.VALID_TYPES)}", str(ctype)))

    att = cfg.get("scope_attestation")
    if att != SCOPE_ATTESTATION:
        issues.append(_err(
            "scope_attestation", "config",
            f'scope_attestation must be present and equal "{SCOPE_ATTESTATION}". '
            "A missing attestation is a hard failure - the generation step has to "
            "state the boundary rather than assume it.",
            str(att),
        ))

    # -- 2. ask ----------------------------------------------------------
    ask = cfg.get("ask")
    if ctype == "cta":
        if not isinstance(ask, dict):
            issues.append(_err("ask", "config", "a cta sequence requires an ask object"))
        else:
            shape = ask.get("shape")
            if shape not in {"link", "email"}:
                issues.append(_err("ask.shape", "config",
                                   'ask.shape must be "link" or "email"', str(shape)))
            if not ask.get("destination"):
                issues.append(_err("ask.destination", "config", "ask.destination is required"))
            if not ask.get("situation"):
                issues.append(_err("ask.situation", "config",
                                   "ask.situation is required - name the reader's situation"))
            dests = {a.get("destination") for a in core.active_asks()}
            if ask.get("destination") and ask["destination"] not in dests:
                issues.append(_err(
                    "ask_ledger", "config",
                    "ask.destination has no active entry in ledgers/asks.json",
                    str(ask.get("destination")),
                ))
    elif ask not in (None, {}):
        issues.append(_err("ask", "config",
                           "ask must be null unless type is cta", str(ask)))

    # -- 3. frames -------------------------------------------------------
    frames = cfg.get("frames") or []
    lo = int(policy.get("min_frames", 5))
    hi = int(policy.get("max_frames", 7))
    if not (lo <= len(frames) <= hi):
        issues.append(_err("frame_count", "config",
                           f"a sequence is {lo} to {hi} frames", str(len(frames))))

    for i, fr in enumerate(frames):
        n = fr.get("n")
        where = f"frame {n if n is not None else i + 1}"

        if n != i + 1:
            issues.append(_err("frame_numbering", where,
                               f"n must be sequential from 1; expected {i + 1}", str(n)))

        continues = bool(fr.get("continues"))
        if continues and i == 0:
            issues.append(_err("continues", where, "frame 1 can never be a continuation"))

        # blocks
        blocks = fr.get("blocks") or []
        if not (1 <= len(blocks) <= 3):
            issues.append(_err("blocks", where, "1 to 3 blocks per frame", str(len(blocks))))

        highlight_count = 0
        frame_stat_span = None

        for bi, blk in enumerate(blocks):
            btxt = blk.get("text") or ""
            bwhere = f"{where} block {bi + 1}"
            if not btxt.strip():
                issues.append(_err("block_text", bwhere, "block text is empty"))
            issues += scan_text(btxt, policy, bwhere)

            size = blk.get("size")
            if bi == 0 and not continues and size not in (None, "big"):
                issues.append(_warn("block_size", bwhere,
                                    "the first block is the headline; size should be big"))
            if size is not None and size not in core.VALID_SIZES:
                issues.append(_err("block_size", bwhere,
                                   f"size must be one of {sorted(core.VALID_SIZES)}", str(size)))

            span = has_statistic(btxt)
            if span:
                frame_stat_span = frame_stat_span or span

            for hl in blk.get("highlights") or []:
                highlight_count += 1
                htxt = (hl.get("text") or "").strip()
                style = hl.get("style")
                if style not in core.VALID_HIGHLIGHT_STYLES:
                    issues.append(_err("highlight_style", bwhere,
                                       f"style must be one of {sorted(core.VALID_HIGHLIGHT_STYLES)}",
                                       str(style)))
                if not htxt:
                    issues.append(_err("highlight_text", bwhere, "highlight text is empty"))
                    continue
                if htxt not in btxt:
                    issues.append(_err("highlight_substring", bwhere,
                                       "highlight text must be an exact substring of its own block",
                                       htxt))
                words = len(htxt.split())
                if not (1 <= words <= 4):
                    issues.append(_err("highlight_length", bwhere,
                                       "a highlight is 1 to 4 words", htxt))

        if highlight_count > 1:
            issues.append(_err("one_highlight", where,
                               "at most one highlight per frame - never two on a frame",
                               f"{highlight_count} highlights"))

        # source line
        src_line = fr.get("source_line")
        issues += scan_text(src_line or "", policy, f"{where} source_line")
        if frame_stat_span and not (src_line or "").strip():
            issues.append(_err(
                "statistic_requires_source", where,
                "a block carrying a statistic requires a non-null source_line on that "
                "frame. A number without a source does not render.",
                frame_stat_span,
            ))

        # background
        bg = fr.get("background")
        if continues:
            if bg is not None:
                issues.append(_warn("continues_background", where,
                                    "continuation frames inherit the background; omit it"))
            if fr.get("text_position") is not None:
                issues.append(_warn("continues_anchor", where,
                                    "continuation frames inherit the anchor; omit text_position"))
            for comp in ("eyebrow", "metrics"):
                if fr.get(comp):
                    issues.append(_warn("continues_component", where,
                                        f"a continuation frame should not restate "
                                        f"{comp}; it belongs on the frame that opens "
                                        f"the chain"))
        else:
            if not isinstance(bg, dict):
                issues.append(_err("background", where,
                                   "background is required on every non-continuation frame"))
            else:
                btype = bg.get("type")
                if btype == "photo" or bg.get("src"):
                    issues.append(_err(
                        "background_photo_retired", where,
                        'photo backgrounds no longer exist. Every frame is drawn from '
                        'config/brand.json. Replace this with {"type": "field"} (or '
                        '"note" for the full capital-markets-note chrome) and drop src, '
                        'zoom and focus.',
                        str(bg.get("src") or btype),
                    ))
                elif btype not in core.VALID_BACKGROUND_TYPES:
                    issues.append(_err("background_type", where,
                                       f"background.type must be one of "
                                       f"{sorted(core.VALID_BACKGROUND_TYPES)}", str(btype)))

            tp = fr.get("text_position")
            if tp is not None and tp not in core.VALID_TEXT_POSITIONS:
                issues.append(_err("text_position", where,
                                   f"text_position must be one of "
                                   f"{sorted(core.VALID_TEXT_POSITIONS)}", str(tp)))

        # note components
        issues += validate_metrics(fr.get("metrics"), policy, where)
        issues += validate_chart(fr.get("chart"), policy, where)
        issues += validate_bullets(fr.get("bullets"), policy, where)
        issues += validate_signal(fr.get("signal"), policy, where)

        eyebrow = fr.get("eyebrow")
        if eyebrow is not None:
            if not str(eyebrow).strip():
                issues.append(_err("eyebrow", where, "eyebrow is present but empty"))
            elif len(str(eyebrow)) > 48:
                issues.append(_warn("eyebrow_length", where,
                                    "an eyebrow is a dateline, not a sentence - keep it "
                                    "under 48 characters", str(eyebrow)))
            issues += scan_text(str(eyebrow), policy, f"{where} eyebrow")

        # a frame that plots numbers is a frame that cites them
        chart = fr.get("chart")
        has_numbers = bool(chart) or bool(fr.get("metrics"))
        cited = (bool((src_line or "").strip())
                 or bool((chart or {}).get("source"))
                 or bool(str(fr.get("data_sources") or "").strip()))
        if has_numbers and not cited:
            issues.append(_err(
                "statistic_requires_source", where,
                "a frame carrying a chart or metric cards requires a source - set "
                "source_line or data_sources on the frame, or source inside the chart "
                "object. A plotted number without a source does not render, exactly "
                "like a written one.",
                "chart" if chart else "metrics",
            ))

        # artifact
        art = fr.get("artifact")
        if art:
            if core.resolve_artifact(art) is None:
                issues.append(_err(
                    "artifact_path", where,
                    "artifact must be a filename from assets/artifacts/ only. No path "
                    "outside that folder may be composited. This is the structural "
                    "block on a client screenshot ever reaching a frame.",
                    str(art),
                ))
            pos = fr.get("artifact_pos")
            if pos and pos not in {"lower", "center", "upper"}:
                issues.append(_err("artifact_pos", where,
                                   "artifact_pos must be lower, center or upper", str(pos)))

        # sticker
        st = fr.get("sticker")
        if st is not None:
            if not isinstance(st, dict) or st.get("kind") not in {"poll", "link"}:
                issues.append(_err("sticker", where,
                                   'sticker must be null or {"kind":"poll"|"link", ...}',
                                   str(st)))

    # -- 4. chain-level rules -------------------------------------------
    # no more than three beats on one background
    chain = 0
    for fr in frames:
        if fr.get("continues"):
            chain += 1
            if chain >= 3:
                issues.append(_warn("chain_depth", f"frame {fr.get('n')}",
                                    "never more than three beats on one background"))
        else:
            chain = 0

    # a panel frame cannot be continued
    for prev, nxt in zip(frames, frames[1:]):
        panel = [k for k in ("chart", "metrics", "bullets", "signal") if prev.get(k)]
        if panel and nxt.get("continues"):
            issues.append(_err(
                "panel_not_continuable", f"frame {nxt.get('n')}",
                f"frame {prev.get('n')} carries a {panel[0]} panel, so it cannot be "
                "continued. A continuation redraws the opening frame's background and "
                "dims its text; a chart is neither, and would either vanish or collide "
                "with the new beat. Give this beat its own background.",
                f"continues frame {prev.get('n')}"))

    # cta ending
    if ctype == "cta" and frames:
        last = frames[-1]
        if last.get("role") != "cta":
            issues.append(_err("cta_ending", f"frame {last.get('n')}",
                               'a cta sequence must end on frame N with role "cta"',
                               str(last.get("role"))))
        for fr in frames:
            if fr.get("role") == "cta":
                blob = " ".join((b.get("text") or "") for b in fr.get("blocks") or [])
                if not policy.get("keyword_ctas_allowed", False) and KEYWORD_ASK.search(blob):
                    issues.append(_err(
                        "keyword_cta", f"frame {fr.get('n')}",
                        "keyword-shaped asks are refused while keyword_ctas_allowed is "
                        "false. Keyword replies route into DMs - wrong channel, and an "
                        "unarchived communication trail.",
                        KEYWORD_ASK.search(blob).group(0),
                    ))
    if ctype != "cta":
        for fr in frames:
            if fr.get("role") == "cta":
                issues.append(_err("cta_role", f"frame {fr.get('n')}",
                                   "only a cta sequence may carry a cta frame"))

    return issues


def errors(issues) -> list[Issue]:
    return [i for i in issues if i["level"] == "error"]


def warnings(issues) -> list[Issue]:
    return [i for i in issues if i["level"] == "warning"]


def format_issues(issues, slug: str = "") -> str:
    if not issues:
        return f"OK  {slug}".rstrip()
    lines = []
    for i in issues:
        tag = "ERROR  " if i["level"] == "error" else "warning"
        span = f'   >>> "{i["span"]}"' if i.get("span") else ""
        lines.append(f'  {tag} [{i["rule"]}] {i["where"]}: {i["message"]}{span}')
    head = f"{slug}:" if slug else ""
    return "\n".join([head] + lines) if head else "\n".join(lines)


# --------------------------------------------------------------------------
# week-level cross validation
# --------------------------------------------------------------------------

def check_week(slugs: list[str], policy: dict | None = None) -> list[Issue]:
    """Cross-validate a batch for duplicate asks, chart monotony and headline reuse.

    Asset reuse used to be the thing this caught, back when frames sat on photos out
    of a shared library. Backgrounds are drawn now, so there is no photo to reuse -
    the batch-level risk moved to *sameness*: five sequences in a week that all open
    on a bar chart read as one template, not five arguments."""
    policy = policy or core.load_policy()
    issues: list[Issue] = []
    ask_owner: dict[str, str] = {}
    headline_owner: dict[str, str] = {}
    chart_count = 0
    cta_count = 0

    for slug in slugs:
        try:
            cfg = core.load_config(slug)
        except FileNotFoundError:
            issues.append(_err("config", slug, "config.json missing"))
            continue

        if cfg.get("type") == "cta":
            cta_count += 1
            dest = (cfg.get("ask") or {}).get("destination")
            if dest:
                if dest in ask_owner:
                    issues.append(_err("duplicate_ask", slug,
                                       f"same ask destination as {ask_owner[dest]}", str(dest)))
                else:
                    ask_owner[dest] = slug

        frames = cfg.get("frames", [])
        if any(fr.get("chart") for fr in frames):
            chart_count += 1

        if frames:
            first = frames[0].get("blocks") or [{}]
            head = " ".join(str(first[0].get("text") or "").lower().split())
            # "[hook] write this beat" is an unwritten frame, not a duplicate one -
            # a scaffold repeated across drafts is expected and says nothing about
            # whether the finished week repeats itself
            if head and not head.startswith("["):
                if head in headline_owner:
                    issues.append(_err(
                        "duplicate_headline", slug,
                        f"opens on the same headline as {headline_owner[head]}", head[:60]))
                else:
                    headline_owner[head] = slug

    if cta_count > 1:
        issues.append(_err("cta_rhythm", "batch",
                           "at most one sequence per week is type cta "
                           "(4 non-ask sequences for every 1 ask)", f"{cta_count} cta sequences"))

    if len(slugs) >= 3 and chart_count == len(slugs):
        issues.append(_warn(
            "chart_monotony", "batch",
            "every sequence this week carries a chart. A chart is the strongest move "
            "available and it dulls with repetition - a week where the data frame is "
            "the exception reads as evidence, a week where it is the rule reads as a "
            "template.", f"{chart_count}/{len(slugs)}"))
    return issues
