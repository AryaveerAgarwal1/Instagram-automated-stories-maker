#!/usr/bin/env python3
"""Start the local review app.

    python run.py                 http://127.0.0.1:8045
    python run.py --port 9000
    python run.py --no-browser

Local only. It binds to 127.0.0.1 by design: this app writes approval.json, and
the approval gate assumes the person clicking approve is the named human sitting
at this machine.
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def preflight() -> None:
    missing = []
    for mod, pkg in (("PIL", "pillow"), ("fastapi", "fastapi"), ("uvicorn", "uvicorn")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print("Missing dependencies: " + ", ".join(missing))
        print("Install them with:\n\n    pip install -r requirements.txt\n")
        raise SystemExit(1)

    if not (ROOT / "assets" / "artifacts" / "INDEX.md").exists():
        print("No artifact library yet. Generating placeholder artifact pages...\n")
        import tools.seed_assets as seed  # noqa: F401
        sys.argv = ["seed_assets.py"]
        seed.main()
        print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8045)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    args = ap.parse_args()

    preflight()

    from s45core import core

    policy = core.load_policy()
    ok, why = core.policy_registration_ready(policy)

    url = f"http://{args.host}:{args.port}"
    print("=" * 68)
    print("  s45 Content Factory - local review app")
    print(f"  {url}")
    print("=" * 68)
    if not ok:
        print("  IDENTITY BLOCK HARD STOP is active:")
        print(f"    {why}")
        print("  Nothing will render until config/policy.json is filled in.")
    if str(policy.get("entity_status")) == "TBD_BY_COUNSEL":
        print("  entity_status is TBD_BY_COUNSEL. Q1 and Q2 in the skill file must be")
        print("  answered by Indian counsel before the first post.")
    print("  Ctrl+C to stop.\n")

    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    import uvicorn
    uvicorn.run("server.app:app", host=args.host, port=args.port,
                reload=args.reload, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
