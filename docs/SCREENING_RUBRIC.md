# Screening Rubric — the decision function

**Every role must clear all three gates, in order, before it reaches your
review or a send queue.** Role fit is only the first layer; company quality and
product prospects are what actually kill roles at send-time. Direction truth
lives in `config/profile.yaml`; this file is the per-candidate checklist.

## Three gates (evaluate in order; stop at the first failure)

### Gate 1 · Role direction (read the JD body, not the list title)

List titles get cross-wired with sidebar recommendations — only trust the JD
body (`.job-sec-text`).

- ✅ On-target (sample persona): data/AI-driven user growth (strategy/product
  side), AI product-ops (product side), AI product assistant / junior PM,
  language-learning / education product.
- ❌ Reject: content/AIGC/creator/short-drama ops; community ops; pure
  media-buying growth; sales/BD/advisor with commission; 3–5y / 5–10y hard
  requirements; generic PM (traditional tooling, no AI/growth ownership);
  heavy-engineering (must write code / CS algorithms / RAG); explicit CS major
  requirement.
- 2 years experience = soft (you can stretch; be honest); 应届 / 经验不限 /
  1–3y preferred.
- Code: `rules.hard_filter_reasons()` + `rules.classify_archetype()`.

> Adapt the ✅/❌ lists to your own targets via `config/profile.yaml`
> (`lexicon`, `hard_filters`, `search.keywords`).

### Gate 2 · Company quality (read the company page first, not at send-time)

- ❌ **Founded this year / < 2 years** — too new, red flag.
- ❌ **0–20 people + unfunded/angel** — micro early-stage, no revenue engine.
- ❌ **单休 / 996 / 大小周 / after-hours availability** — work-schedule red line.
- ❌ **Outsourcing / on-site dispatch / staffing body**.
- ❌ **Call center / 电销 / 客服中心**.
- ⚠️ **HR inactive for months** — downgrade (likely zombie posting).
- Code: `rules.company_quality_flags(facts, jd, company)`; facts come from
  `browser/cdp_company.mjs` → `data/company_facts.json`. Thresholds are config
  (`company_quality:` in profile.yaml).

### Gate 3 · Product moat & major fit (judgment call — human in the loop)

- ❌ **No competitive moat / no prospect** — clearly can't beat the incumbents
  (look at the market structure, not just the JD).
- ❌ **Can't tell what AI they actually build** — vague JD, unclear product.
- ❌ **Low major relevance** — role clearly off your background.
- ✅ Bonus: the role hangs directly onto your real evidence (your portfolio,
  measurable wins, working language, domain).

This gate cannot be fully scripted; it is why the system emits a *packet for
human judgment* instead of auto-approving.

## Other deterministic conditions

Salary floor below your `hard_filters.salary_floor_min_k` → reject. Cities from
`search.cities`. Full-time only (no internship/part-time/short-term).

## North star (don't get dragged by "10 a day")

The goal is **offers, not sending 10 cold greetings**. Under strict gates you may
not fill a daily quota with clean roles — that's fine. Prefer three deeply
researched, on-target roles over letting a bad one back into the funnel. The real
funnel metric is reply/interview rate, not send volume.
