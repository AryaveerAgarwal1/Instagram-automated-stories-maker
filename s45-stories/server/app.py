"""FastAPI backend for the s45 story review app.

Local only. It is a thin, honest wrapper over the same code the CLI uses - the
renderer, the validator, the approval gate - so nothing the UI does can bypass a
rule the CLI enforces.

    python run.py            (then open http://127.0.0.1:8045)
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from s45core import core, render_engine, validate  # noqa: E402

import archive as archive_mod  # noqa: E402
import schedule as schedule_mod  # noqa: E402

WEB_DIR = core.ROOT / "web"

app = FastAPI(title="s45 Content Factory", version="1.0")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def issue_payload(issues) -> list[dict]:
    return [dict(i) for i in issues]


def sequence_payload(slug: str, with_validation: bool = True) -> dict:
    policy = core.load_policy()
    cfg = core.load_config(slug)
    st = core.sequence_status(slug)
    out = {**st, "config": cfg}
    if with_validation:
        issues = validate.validate_config(cfg, slug, policy)
        out["issues"] = issue_payload(issues)
        out["error_count"] = len(validate.errors(issues))
        out["warning_count"] = len(validate.warnings(issues))
    return out


def policy_payload() -> dict:
    policy = core.load_policy()
    ok, why = core.policy_registration_ready(policy)
    return {
        "policy": policy,
        "identity_block": {
            "ready": ok,
            "reason": why,
            "lines": core.identity_block_lines(policy),
        },
        "entity_status_pending": str(policy.get("entity_status")) == "TBD_BY_COUNSEL",
    }


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------

@app.get("/api/state")
def get_state():
    policy = core.load_policy()
    slugs = core.list_sequence_slugs()

    seqs = []
    for s in slugs:
        try:
            seqs.append(sequence_payload(s))
        except Exception as e:  # a broken config should not blank the whole UI
            seqs.append({"slug": s, "state": "broken", "error": str(e),
                         "issues": [], "error_count": 1, "warning_count": 0,
                         "config": {}, "rendered_frames": []})

    art_index = core.read_index(core.ARTIFACTS_DIR)

    artifacts = [{"name": n, "description": art_index.get(n, "")}
                 for n in core.list_artifacts()]

    return {
        **policy_payload(),
        "brand": core.load_brand(),
        "sequences": seqs,
        "ideas": core.load_ideas().get("ideas", []),
        "asks": core.load_asks().get("asks", []),
        "artifacts": artifacts,
        "week_issues": issue_payload(validate.check_week(slugs, policy)),
    }


@app.get("/api/sequences/{slug}")
def get_sequence(slug: str):
    try:
        return sequence_payload(slug)
    except FileNotFoundError:
        raise HTTPException(404, f"no sequence {slug}")


# --------------------------------------------------------------------------
# editing
# --------------------------------------------------------------------------

class ConfigBody(BaseModel):
    config: dict[str, Any]


@app.put("/api/sequences/{slug}/config")
def put_config(slug: str, body: ConfigBody):
    d = core.sequence_dir(slug)
    if not d.exists():
        raise HTTPException(404, f"no sequence {slug}")
    core.write_json(d / "config.json", body.config)
    return sequence_payload(slug)


class NewSequence(BaseModel):
    slug: str
    type: str = "thesis"
    highlight_title: str = "How we think"
    from_idea: str | None = None


@app.post("/api/sequences")
def new_sequence(body: NewSequence):
    slug = body.slug.strip().lower().replace(" ", "-")
    d = core.sequence_dir(slug)
    if (d / "config.json").exists():
        raise HTTPException(409, f"{slug} already exists")
    (d / "sources").mkdir(parents=True, exist_ok=True)

    def frame(n, role, text, bg=None, continues=False):
        f = {"n": n, "role": role,
             "blocks": [{"text": text}],
             "artifact": None, "artifact_pos": None,
             "source_line": None, "sticker": None}
        if continues:
            f["continues"] = True
        else:
            f["background"] = bg or {"type": "field"}
            f["text_position"] = "top"
        return f

    roles = {
        "private_markets": ["hook", "read", "read", "mechanism", "mechanism", "implication"],
        "thesis": ["hook", "argument", "argument", "argument", "evidence", "counter"],
        "build": ["hook", "context", "context", "detail", "detail", "learned"],
        "cta": ["hook", "argument", "argument", "argument", "bridge", "cta"],
    }.get(body.type, ["hook", "argument", "argument", "argument", "evidence", "counter"])

    frames = []
    for i, role in enumerate(roles, start=1):
        cont = i in (2, 4)
        frames.append(frame(i, role, f"[{role}] write this beat", continues=cont))

    cfg = {
        "slug": slug,
        "type": body.type,
        "ask": None,
        "scope_attestation": "private_markets_only",
        "highlight_title": body.highlight_title,
        "profile": {"handle": "@s45"},
        "frames": frames,
    }
    if body.type == "cta":
        cfg["ask"] = {"shape": "link", "destination": "", "situation": ""}

    core.write_json(d / "config.json", cfg)

    if body.from_idea:
        data = core.load_ideas()
        for it in data.get("ideas", []):
            if it.get("id") == body.from_idea:
                it["status"] = "building"
                it["slug"] = slug
        core.save_ideas(data)

    return sequence_payload(slug)


# --------------------------------------------------------------------------
# validate / render
# --------------------------------------------------------------------------

@app.post("/api/sequences/{slug}/validate")
def post_validate(slug: str):
    return sequence_payload(slug)


class RenderBody(BaseModel):
    frame: int | None = None


@app.post("/api/sequences/{slug}/render")
def post_render(slug: str, body: RenderBody | None = None):
    frame = body.frame if body else None
    try:
        res = render_engine.render_sequence(slug, only_frame=frame)
    except render_engine.RenderError as e:
        return {"ok": False, "error": str(e), **sequence_payload(slug)}
    except FileNotFoundError:
        raise HTTPException(404, f"no sequence {slug}")
    return {"ok": True, "render": res, **sequence_payload(slug)}


@app.get("/api/sequences/{slug}/post-order")
def get_post_order(slug: str):
    p = core.sequence_dir(slug) / "post-order.md"
    if not p.exists():
        raise HTTPException(404, "render first")
    return {"markdown": p.read_text(encoding="utf-8")}


# --------------------------------------------------------------------------
# approval
# --------------------------------------------------------------------------

class ApproveBody(BaseModel):
    approver: str
    note: str = ""


@app.post("/api/sequences/{slug}/approve")
def post_approve(slug: str, body: ApproveBody):
    """Writes a properly hashed approval.json with the approver's identity.

    The approver is a named human choosing from policy.approvers in the UI. The
    generator never calls this endpoint and the file records that a human did.
    """
    policy = core.load_policy()
    if body.approver not in (policy.get("approvers") or []):
        raise HTTPException(400, "approver is not in policy.approvers")

    d = core.sequence_dir(slug)
    hashes = core.frame_hashes(d)
    if not hashes:
        raise HTTPException(400, "nothing rendered to approve")

    issues = validate.validate_config(core.load_config(slug), slug, policy)
    if validate.errors(issues):
        raise HTTPException(400, "sequence does not validate; fix the errors first")

    core.write_json(core.approval_path(slug), {
        "slug": slug,
        "approver": body.approver,
        "approved_at": core.now_iso(),
        "note": body.note,
        "source": "review-app",
        "author": "human",
        "frame_hashes": hashes,
    })
    render_engine.write_post_order(slug, core.load_config(slug), policy)
    return sequence_payload(slug)


@app.delete("/api/sequences/{slug}/approve")
def delete_approve(slug: str):
    p = core.approval_path(slug)
    if p.exists():
        p.unlink()
    render_engine.write_post_order(slug, core.load_config(slug), core.load_policy())
    return sequence_payload(slug)


# --------------------------------------------------------------------------
# publish / archive
# --------------------------------------------------------------------------

class ScheduleBody(BaseModel):
    mode: str = "dry-run"          # dry-run | hand-posted | publish


@app.post("/api/sequences/{slug}/schedule")
def post_schedule(slug: str, body: ScheduleBody):
    policy = core.load_policy()
    try:
        if body.mode == "hand-posted":
            seq = core.sequence_dir(slug)
            cfg = core.load_config(slug)
            approval = core.read_json(core.approval_path(slug), default=None)
            if not approval:
                raise schedule_mod.Refusal(f"{slug}: NOT PUBLISHABLE. no approval.json.")
            if approval.get("approver") not in (policy.get("approvers") or []):
                raise schedule_mod.Refusal(f"{slug}: INVALID APPROVAL. approver not in "
                                           "policy.approvers.")
            if core.frame_hashes(seq) != (approval.get("frame_hashes") or {}):
                raise schedule_mod.Refusal(f"{slug}: APPROVAL INVALIDATED. frames changed "
                                           "after approval.")
            rec = core.read_json(core.schedule_record_path(slug), default=None)
            if rec and rec.get("published_at"):
                raise schedule_mod.Refusal(f"{slug}: ALREADY PUBLISHED at "
                                           f"{rec['published_at']}.")
            schedule_mod.record(slug, cfg, core.frame_hashes(seq), "hand-posted")
            msg = "Recorded as hand-posted. Archive it now."
        else:
            state = schedule_mod.check_publishable(slug, policy)
            if body.mode == "dry-run":
                msg = (f"Every gate passed. Would push "
                       f"{len(state['frames'])} frames as one story post, in order. "
                       f"Approved by {state['approval']['approver']}.")
            else:
                schedule_mod.record(slug, state["config"], state["frames"], "scheduled")
                msg = "Published (recorded). Archive it now."
    except schedule_mod.Refusal as e:
        return {"ok": False, "message": str(e), **sequence_payload(slug)}
    return {"ok": True, "message": msg, **sequence_payload(slug)}


@app.post("/api/sequences/{slug}/archive")
def post_archive(slug: str):
    try:
        dest = archive_mod.archive_sequence(slug)
    except (RuntimeError, FileNotFoundError) as e:
        return {"ok": False, "message": str(e), **sequence_payload(slug)}
    return {"ok": True, "message": f"Archived to {dest.relative_to(core.ROOT)} with a "
                                   f"SHA-256 manifest.", **sequence_payload(slug)}


# --------------------------------------------------------------------------
# ideas
# --------------------------------------------------------------------------

class IdeaBody(BaseModel):
    title: str
    type: str = "thesis"
    note: str = ""


@app.post("/api/ideas")
def add_idea(body: IdeaBody):
    data = core.load_ideas()
    ideas = data.setdefault("ideas", [])
    ideas.append({
        "id": f"idea-{len(ideas) + 1}-{int(core.today().toordinal())}",
        "title": body.title, "type": body.type, "status": "queued", "note": body.note,
    })
    core.save_ideas(data)
    return {"ideas": ideas}


class IdeaPatch(BaseModel):
    status: str


@app.patch("/api/ideas/{idea_id}")
def patch_idea(idea_id: str, body: IdeaPatch):
    data = core.load_ideas()
    for it in data.get("ideas", []):
        if it.get("id") == idea_id:
            it["status"] = body.status
    core.save_ideas(data)
    return {"ideas": data.get("ideas", [])}


# --------------------------------------------------------------------------
# images
# --------------------------------------------------------------------------

def _thumb(path: Path, width: int) -> Response:
    with Image.open(path) as im:
        im = im.convert("RGB")
        h = max(1, int(im.height * width / im.width))
        im = im.resize((width, h), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
    return Response(buf.getvalue(), media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@app.get("/api/frame/{slug}/{name}")
def get_frame(slug: str, name: str, w: int = 0):
    p = core.sequence_dir(slug) / Path(name).name
    if not p.exists() or p.suffix != ".png":
        raise HTTPException(404, "no such frame")
    if w:
        return _thumb(p, min(w, 1080))
    return FileResponse(p, media_type="image/png",
                        headers={"Cache-Control": "no-store"})


@app.get("/api/asset/{kind}/{name}")
def get_asset(kind: str, name: str, w: int = 360):
    if kind == "artifacts":
        p = core.resolve_artifact(name)
    else:
        raise HTTPException(404, "unknown asset kind")
    if p is None:
        raise HTTPException(404, "no such asset")
    return _thumb(p, min(w, 1440))


# --------------------------------------------------------------------------
# static
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")


app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")
