#!/usr/bin/env python3
"""Render a decision-ready batch: inverted-pyramid cards (结论先行).

Each card leads with a verdict, then a company health line, then the one driving
reason and the single biggest risk, so you confirm in ~15s. A role belongs here
only once it is decision-ready: role-fit + company vetted. Cards are explicitly
marked 公司未核 when company facts are missing (trust calibration).

Run:  python3 -m agent.render_decision_batch [--status shortlisted,approved]
"""

from __future__ import annotations

import argparse
from datetime import date

from .config import COMPANY_FACTS, JD_READS, ROOT
from .ledger import load_json, read_rows
from .rules import company_quality_flags, decode_boss_digits, parse_score

OUT = ROOT / "Decision Batch.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default="shortlisted,approved")
    args = ap.parse_args()
    statuses = {s.strip() for s in args.status.split(",")}

    rows = [r for r in read_rows() if r["status"] in statuses]
    jd_by_url = {j["url"]: j for j in load_json(JD_READS, [])}
    facts_by_url = load_json(COMPANY_FACTS, {})

    def card(r):
        url = r["job_url"]
        jd_text = decode_boss_digits((jd_by_url.get(url, {}) or {}).get("jd", "") or "")
        facts = facts_by_url.get(url)
        score = parse_score(r["match_score"]) or 0
        cq = company_quality_flags(facts, jd_text, r["company"])

        if facts:
            checkup = " · ".join(x for x in [
                f"成立{facts.get('founded','?')[:4]}" if facts.get("founded") else "成立?",
                facts.get("size") or "规模?", facts.get("funding") or "融资?",
            ] if x)
            checkup += "  " + ("🔴 " + "；".join(cq) if cq else "✅ 无红线")
        else:
            checkup = "⚠️ 公司未核（待 cdp_company.mjs 体检）"
            if cq:
                checkup += " · 🔴 " + "；".join(cq)

        if cq:
            verdict = "不投/再想"
        elif score >= 4 and facts:
            verdict = "建议投"
        elif not facts:
            verdict = "待核公司"
        else:
            verdict = "再想"

        sal = decode_boss_digits(r.get("salary", ""))
        head = f"### [{verdict}] {r['company']} · {r['title'][:30]} · {sal} · {r['city'][:8]} · {r['experience'] or '经验不限'}"
        lines = [head, f"- **公司体检**：{checkup}"]
        if r.get("fit_reason"):
            lines.append(f"- **为什么**：{r['fit_reason']}")
        risk = cq[0] if cq else (r.get("notes", "").split("门槛:")[-1][:60] if "门槛:" in r.get("notes", "") else "")
        if risk:
            lines.append(f"- **最大风险**：{risk}")
        lines.append(f"- 🔗 {url}")
        return "\n".join(lines), verdict

    body = [f"# Decision Batch {date.today().isoformat()}", "",
            "> 结论先行的决策就绪批次。`建议投`=公司已核+高分；`待核公司`=缺体检；`不投/再想`=踩红线。",
            "> 回 `approve 公司名` / `skip ...`；approved 的进 Send Queue 发送。", ""]
    if not rows:
        body.append("_当前无 shortlisted/approved 岗位。_")
    else:
        order = {"建议投": 0, "再想": 1, "待核公司": 2, "不投/再想": 3}
        cards = [card(r) for r in rows]
        cards.sort(key=lambda c: order.get(c[1], 9))
        body += [c for c, _ in cards]
    OUT.write_text("\n\n".join(body) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} cards)")


if __name__ == "__main__":
    main()
