#!/usr/bin/env python3
"""Load the candidate profile and resolve repo paths.

The profile is the single source of personalization. We look for
``config/profile.yaml`` (your private copy, gitignored) and fall back to
``config/profile.example.yaml`` with a warning so a fresh checkout still runs.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG_DIR = ROOT / "config"
PROFILE = CONFIG_DIR / "profile.yaml"
PROFILE_EXAMPLE = CONFIG_DIR / "profile.example.yaml"

# Canonical ledger + intermediate caches (all under data/, all gitignored).
LEDGER = DATA / "applications.csv"
SEARCH_PAGE = DATA / "current_page.json"
SEARCH_READS = DATA / "search_reads"
JD_TODO = DATA / "_jd_todo.json"
JD_READS = DATA / "_jd_reads.json"
COMPANY_FACTS = DATA / "company_facts.json"
BATCH_PACKET = DATA / "_batch_packet.json"
OPEN_URLS = DATA / "_open_urls.json"
GREETINGS = DATA / "greetings.json"
LLM_EVALS = DATA / "llm_evals.json"
REPORT_DIR = ROOT / "reports"
JOB_EVAL_DIR = REPORT_DIR / "job_evaluations"


@lru_cache(maxsize=1)
def load_profile() -> dict[str, Any]:
    """Return the parsed profile dict. Cached for the process lifetime."""
    try:
        import yaml
    except ImportError:  # pragma: no cover
        sys.exit("PyYAML is required: pip install -r requirements.txt")

    path = PROFILE if PROFILE.exists() else PROFILE_EXAMPLE
    if path is PROFILE_EXAMPLE:
        print(
            "! config/profile.yaml not found; using profile.example.yaml. "
            "Copy it to config/profile.yaml and edit before a real run.",
            file=sys.stderr,
        )
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def lex(name: str) -> list[str]:
    """Return a lowercased lexicon list by key (empty if missing)."""
    terms = (load_profile().get("lexicon") or {}).get(name) or []
    return [str(t).lower() for t in terms]


def cfg(*keys: str, default: Any = None) -> Any:
    """Nested profile lookup: cfg('scoring', 'tier_base', default={...})."""
    node: Any = load_profile()
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def ensure_dirs() -> None:
    for d in (DATA, SEARCH_READS, REPORT_DIR, JOB_EVAL_DIR):
        d.mkdir(parents=True, exist_ok=True)
