#!/usr/bin/env python3
"""Persist LLM (in-session) JD judgments into the ledger + evaluation reports.

The intelligence upgrade: instead of keyword scoring, the in-session LLM reads
each JD, judges fit against your profile, and records score + archetype + reasons
+ risks + verdict. This writes that judgment so the approval queue / dashboard
pick it up like any JD-reviewed role. Keyword rules remain a hard safety net:
if a role hits a hard filter, we refuse to shortlist it regardless of LLM score.

Input: data/llm_evals.json — a list of objects:
  {"url": "<job_url>", "score": 4.6, "archetype": "AI 产品运营（产品侧）",
   "verdict": "shortlist",            # shortlist | discovered | skip
   "fit": "一句话匹配判断",
   "positives": ["..."], "risks": ["..."], "reasoning": "判断理由"}

Run:  python3 -m agent.llm_eval [--file data/llm_evals.json]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .config import JD_READS, JOB_EVAL_DIR, LLM_EVALS, ROOT
from .ledger import load_json, read_rows, today, write_rows
from .rules import decode_boss_digits, hard_filter_reasons, score_text


def slug(text: str) -> str:
    s = re.sub(r"[^\w一-鿿]+", "-", (text or "").strip().lower())
    return s.strip("-")[:40] or "x"


def jd_text_by_url() -> dict[str, str]:
    out: dict[str, str] = {}
    for d in load_json(JD_READS, []):
        if d.get("url") and d.get("jd"):
            out[d["url"]] = decode_boss_digits(d["jd"])
    return out


def append_note(existing: str, note: str) -> str:
    existing = (existing or "").strip()
    if note in existing:
        return existing
    return f"{existing} | {note}".strip(" |")[:900]


def build_report(row, ev, jd, next_status) -> str:
    positives = ev.get("positives") or []
    risks = ev.get("risks") or []
    jd_excerpt = "\n".join(f"- {ln.strip()}" for ln in (jd or "").splitlines() if ln.strip())[:1500]
    return f"""# {row.get('company') or '(unknown)'} - {row.get('title') or '(role)'} LLM Evaluation

Date: {today()}

## Verdict

| Field | Value |
|---|---|
| Score | {score_text(float(ev['score']))} |
| Archetype | {ev.get('archetype', '')} |
| Decision | {ev.get('verdict', '')} |
| Ledger status | `{next_status}` |
| URL | {row.get('job_url', '')} |

## Fit Summary

- 判断：{ev.get('fit', '')}
- Positives: {"；".join(positives) if positives else "—"}
- Risks: {"；".join(risks) if risks else "无明显风险"}

## Positive Evidence From JD

{chr(10).join(f"- {p}" for p in positives) if positives else "- No clear positive JD evidence captured."}

## Risk Evidence From JD

{chr(10).join(f"- {r}" for r in risks) if risks else "- No explicit hard-filter risk captured."}

## JD Excerpt

{jd_excerpt or "- No JD excerpt captured."}

## LLM Judgment

{ev.get('reasoning', '(no reasoning provided)')}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(LLM_EVALS))
    args = ap.parse_args()

    evals = json.loads(Path(args.file).read_text(encoding="utf-8"))
    rows = read_rows()
    by_url = {r.get("job_url"): r for r in rows}
    by_id = {r.get("id"): r for r in rows}
    jd_map = jd_text_by_url()
    JOB_EVAL_DIR.mkdir(parents=True, exist_ok=True)

    applied = vetoed = 0
    for ev in evals:
        row = by_url.get(ev.get("url")) or by_id.get(ev.get("id"))
        if not row:
            print(f"!! no ledger row for {ev.get('url') or ev.get('id')}")
            continue
        score = float(ev["score"])
        verdict = ev.get("verdict", "discovered")
        hard = hard_filter_reasons(row, ROOT)
        if verdict == "shortlist" and hard:
            verdict = "discovered"
            ev.setdefault("risks", []).append("硬过滤否决：" + "；".join(hard[:2]))
            vetoed += 1
        next_status = {"shortlist": "shortlisted", "skip": "skipped"}.get(verdict, "discovered")

        jd = jd_map.get(ev.get("url"), "")
        report_path = JOB_EVAL_DIR / f"{today()}_{slug(row.get('company', 'company'))}_{slug(row.get('title', 'role'))}.md"
        report_path.write_text(build_report(row, ev, jd, next_status), encoding="utf-8")

        pos = "；".join(ev.get("positives") or [])
        risk = "；".join(ev.get("risks") or [])
        row["match_score"] = score_text(score)
        row["fit_reason"] = (f"加分：{ev.get('fit','')}" + (f"；{pos}" if pos else "")
                             + (f" | 风险：{risk}" if risk else ""))
        row["archetype"] = ev.get("archetype", row.get("archetype", ""))
        row["archetype_conf"] = "LLM判断"
        row["last_checked_at"] = today()
        row["status"] = next_status
        if next_status == "shortlisted":
            row["shortlisted_at"] = row.get("shortlisted_at") or today()
        row["notes"] = append_note(row.get("notes", ""),
                                   f"{today()} LLM eval: {verdict}; report={report_path.relative_to(ROOT)}")
        applied += 1
        print(f"{verdict:11} {score_text(score)} {row.get('company')} / {row.get('title')}")

    write_rows(rows)
    print(f"\nApplied {applied} LLM evals; {vetoed} shortlist(s) vetoed by hard filters.")


if __name__ == "__main__":
    main()
