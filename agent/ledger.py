#!/usr/bin/env python3
"""The canonical ledger: data/applications.csv read/write helpers.

The ledger is the single source of truth for every role's lifecycle. Status
taxonomy (see docs/WORKFLOW.md):
  discovered -> shortlisted -> approved -> applied -> replied -> interview
plus skipped / rejected / expired / risk_blocked / needs_login / error.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from .config import LEDGER
from .rules import FIELDS


def today() -> str:
    return date.today().isoformat()


def make_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def canonical_job_key(url: str) -> str:
    m = re.search(r"/job_detail/([^/.?#]+)", url or "")
    return f"boss:{m.group(1)}" if m else url


def read_rows() -> list[dict[str, str]]:
    if not LEDGER.exists():
        return []
    with LEDGER.open(newline="", encoding="utf-8") as f:
        return [{k: row.get(k, "") for k in FIELDS} for row in csv.DictReader(f)]


def write_rows(rows: list[dict[str, str]]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def read_by_key() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in read_rows():
        if not row.get("job_url"):
            continue
        key = canonical_job_key(row["job_url"])
        existing = out.get(key)
        if not existing or (row.get("last_checked_at") and not existing.get("last_checked_at")):
            out[key] = row
    return out


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default
