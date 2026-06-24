#!/usr/bin/env python3
"""Preflight checks before a screening batch: scripts compile, ledger integrity,
no leaked auth tokens, and generated views still render.

Run:  python3 -m agent.healthcheck
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

from .config import DATA, LEDGER, ROOT
from .ledger import read_rows
from .rules import parse_score

AGENT_DIR = ROOT / "agent"


def ok(m): print(f"OK   {m}")
def warn(m): print(f"WARN {m}")
def fail(m): print(f"FAIL {m}")


def check_compile() -> int:
    errors = 0
    for script in sorted(AGENT_DIR.glob("*.py")):
        try:
            compile(script.read_text(encoding="utf-8"), str(script), "exec")
        except SyntaxError as exc:
            fail(f"compile failed: {script.name}: {exc}"); errors += 1
    if not errors:
        ok("agent/*.py compile")
    return errors


def check_ledger(rows) -> int:
    errors = 0
    if not rows:
        warn("ledger empty (run agent.discover first)"); return 0
    urls = [r.get("job_url", "") for r in rows if r.get("job_url")]
    dups = [u for u, c in Counter(urls).items() if c > 1]
    if dups:
        fail(f"duplicate job_url values: {len(dups)}"); errors += 1
    else:
        ok("no duplicate job URLs")
    no_score = sum(1 for r in rows if parse_score(r.get("match_score")) is None)
    if no_score:
        warn(f"rows missing parseable match_score: {no_score}")
    else:
        ok("all rows have parseable match scores")
    print(f"INFO statuses: {dict(Counter(r.get('status') or 'unknown' for r in rows))}")
    return errors


def check_secrets() -> int:
    errors = 0
    leaks = list(DATA.glob("*auth_token*.json")) + list(DATA.glob("*cookies*.json"))
    if leaks:
        fail(f"auth/cookie files present in data/ (gitignored, but delete): {[p.name for p in leaks]}")
        errors += 1
    else:
        ok("no raw auth/cookie exports in data/")
    return errors


def check_views() -> int:
    errors = 0
    for mod in ("agent.render_dashboard", "agent.weekly_review"):
        proc = subprocess.run([sys.executable, "-m", mod], cwd=ROOT, text=True, capture_output=True)
        if proc.returncode != 0:
            fail(f"{mod} failed: {(proc.stdout + proc.stderr)[:200]}"); errors += 1
    if not errors:
        ok("Dashboard + weekly review render")
    return errors


def main():
    errors = 0
    errors += check_compile()
    errors += check_ledger(read_rows())
    errors += check_secrets()
    errors += check_views()
    if errors:
        fail(f"preflight finished with {errors} error(s)"); raise SystemExit(1)
    ok("preflight clean enough to run a screening batch")


if __name__ == "__main__":
    main()
