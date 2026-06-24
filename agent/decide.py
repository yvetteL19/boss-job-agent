#!/usr/bin/env python3
"""Apply approve/skip decisions to numbered approval-queue rows.

The approval queue is the candidates sorted by score (shortlisted/approved, or
discovered roles that clear score + JD evidence + no hard filter). Numbers match
the rendered Dashboard / Approval Queue order.

Run:  python3 -m agent.decide --approve 1,3 --skip 2 --reason "candidate decision"
"""

from __future__ import annotations

import argparse
import re

from .config import ROOT
from .ledger import read_rows, today, write_rows
from .rules import hard_filter_reasons, parse_score, score_job


def parse_numbers(value: str | None) -> set[int]:
    if not value:
        return set()
    out: set[int] = set()
    for part in re.split(r"[,\s]+", value.strip()):
        if not part:
            continue
        if not part.isdigit():
            raise SystemExit(f"Invalid queue number: {part}")
        out.add(int(part))
    return out


def numeric_score(row) -> float:
    existing = parse_score(row.get("match_score"))
    if existing is not None:
        return existing
    return score_job(row)[0]


def detail_report_exists(row) -> bool:
    matches = re.findall(r"report=([^ |\n]+)", row.get("notes") or "")
    return bool(matches and (ROOT / matches[-1]).exists())


def approval_candidate(row) -> bool:
    status = row.get("status") or ""
    if status in {"shortlisted", "approved"}:
        return True
    return (status == "discovered" and numeric_score(row) >= 3.4
            and detail_report_exists(row) and not hard_filter_reasons(row, ROOT))


def queue_rows(rows):
    return sorted([r for r in rows if approval_candidate(r)], key=numeric_score, reverse=True)


def append_note(row, note):
    existing = (row.get("notes") or "").strip()
    row["notes"] = f"{existing} | {note}" if existing else note


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--approve", help="queue numbers to approve")
    ap.add_argument("--skip", help="queue numbers to skip")
    ap.add_argument("--reason", default="candidate decision from approval queue")
    args = ap.parse_args()

    approve, skip = parse_numbers(args.approve), parse_numbers(args.skip)
    if approve & skip:
        raise SystemExit(f"Cannot both approve and skip: {sorted(approve & skip)}")
    if not approve and not skip:
        raise SystemExit("Provide --approve and/or --skip.")

    rows = read_rows()
    indexed = {i: r for i, r in enumerate(queue_rows(rows), start=1)}
    missing = sorted((approve | skip) - set(indexed))
    if missing:
        raise SystemExit(f"Queue number(s) not found: {missing}. Queue size: {len(indexed)}")

    changed = []
    for n in sorted(approve):
        r = indexed[n]
        r["status"] = "approved"
        r["shortlisted_at"] = r.get("shortlisted_at") or today()
        append_note(r, f"{today()} approval #{n}: approved; {args.reason}")
        changed.append((n, "approved", r.get("company", ""), r.get("title", "")))
    for n in sorted(skip):
        r = indexed[n]
        r["status"] = "skipped"
        append_note(r, f"{today()} approval #{n}: skipped; {args.reason}")
        changed.append((n, "skipped", r.get("company", ""), r.get("title", "")))

    write_rows(rows)
    for n, status, company, title in changed:
        print(f"{n}: {status} - {company} / {title}")


if __name__ == "__main__":
    main()
