#!/usr/bin/env python3
"""Config-driven, role-aware first-touch greeting drafts.

Greetings are human, concise, proof-led: no dashes, no parroting the JD, no
filler, no questions (first touch, not an interview). Templates live in
config/profile.yaml under `greetings.templates`, matched by archetype/title.
For approved roles you usually hand-tune the draft; this is the fast baseline.

Run:  python3 -m agent.greetings --status approved   # writes data/greetings.json
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping

from .config import GREETINGS, cfg
from .ledger import read_rows


def greeting_for(row: Mapping[str, str]) -> str:
    intro = cfg("greetings", "intro", default="你好") or "你好"
    role = str(row.get("title") or "这个岗位")
    archetype = str(row.get("archetype") or "").lower()
    title_l = str(row.get("title") or "").lower()
    templates = cfg("greetings", "templates", default=[]) or []

    default_text = "{intro}。「{role}」挺合我的，想争取一下。"
    for tpl in templates:
        if tpl.get("default"):
            default_text = tpl.get("text", default_text)
            continue
        arch_terms = [t.lower() for t in (tpl.get("when_archetype_contains") or [])]
        title_terms = [t.lower() for t in (tpl.get("when_title_contains") or [])]
        arch_ok = bool(arch_terms) and any(t in archetype for t in arch_terms)
        title_ok = bool(title_terms) and any(t in title_l for t in title_terms)
        if arch_ok or title_ok:
            return tpl.get("text", default_text).format(intro=intro, role=role)
    return default_text.format(intro=intro, role=role)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default="approved")
    args = ap.parse_args()
    statuses = {s.strip() for s in args.status.split(",")}

    existing = {}
    if GREETINGS.exists():
        try:
            existing = json.loads(GREETINGS.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    written = 0
    for r in read_rows():
        if r.get("status") not in statuses:
            continue
        url = r.get("job_url")
        if not url or url in existing:
            continue
        existing[url] = greeting_for(r)
        written += 1
        print(f"- {r.get('company')} / {r.get('title')}\n  {existing[url]}\n")

    GREETINGS.parent.mkdir(parents=True, exist_ok=True)
    GREETINGS.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {GREETINGS} (+{written} new draft(s); edit before sending)")


if __name__ == "__main__":
    main()
