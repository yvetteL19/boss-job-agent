# Architecture

This document explains the design decisions behind boss-job-agent — the parts
worth reusing even if you never run BOSS Zhipin specifically. It is written from
a product perspective: every mechanism here exists to solve a concrete failure
mode observed in real job-hunting.

## The problem this system solves

Job hunting on a Chinese recruiting platform has three structural traps:

1. **Volume bias.** "Apply to more roles" feels productive but tanks quality and
   triggers platform risk control (封号). The right metric is reply/interview
   rate, not send count.
2. **Keyword illusion.** A title with "AI" is not a fit signal. Roles that share
   90% of their JD vocabulary (strategy growth vs. media-buying growth) can be a
   dream job or a burnout trap. Keyword scoring cannot tell them apart.
3. **Decision fatigue.** Reviewing dozens of JDs by hand is the bottleneck. Most
   of that review is re-deciding the same deterministic rejections (too senior,
   wrong city, sketchy company) over and over.

The architecture is nine design moves that each attack one of these.

---

## 1. Profile-as-config (one source of personalization)

`config/profile.yaml` is the **only** place your preferences live. Cities,
keywords, scoring weights, hard filters, company red lines, greeting templates,
and the keyword lexicon are all data, not code. Scripts read it; they never
hardcode a preference.

Why it matters: the same engine serves any candidate by editing one YAML file,
and your private profile (gitignored) never contaminates the shared logic. This
is the classic **two-layer data contract** (see [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md)):
user-owned data vs. system logic, never mixed.

## 2. Archetype-gated band scoring (not keyword sums)

The scorer (`agent/rules.py`) never adds keywords into a number. It runs five
steps:

```
1. classify_archetype(row, jd)  -> (label, tier, confidence, reasons)
2. score = tier_base[tier]                      # A=4.0 B=3.5 C=2.9 D=2.0
3. score += bounded_evidence_modifiers          # clamped to [-0.8, +0.8], never crosses a tier
4. score = min(score, *hard_caps)               # JD-aware: experience years, opacity, content/community, ...
5. score = min(score, confidence_gates)         # no-JD cap 4.2; low-confidence cap 3.4
```

The insight: **what a role *is*** (its archetype/tier) dominates; evidence only
nudges within the band. An "AI" keyword can never manufacture a high score for a
structurally wrong role. Tiers:

| Tier | Meaning | Base | Behavior |
|---|---|---:|---|
| A | core targets | 4.0 | can enter queue, still flagged for risk |
| B | conditional buffer | 3.5 | queue only if JD evidence supports it |
| C | weak / usually wrong | 2.9 (cap 3.2) | discovery backlog, not approval |
| D | hard reject | 2.0 (cap 2.4) | skip |
| unknown | insufficient signal | 3.2 (cap 3.4) | mark for human |

All bases, weights and caps are config (`scoring:` in profile.yaml).

## 3. LLM-as-judge over keyword rules

Keyword rules are a **safety net**, not the brain. The real fit call is made by
an LLM that reads the JD body and judges it against your profile, writing back a
score + archetype + reasons + risks (`agent/llm_eval.py`, input
`data/llm_evals.json`). This is what distinguishes "strategy growth" (Tier A)
from "media-buying growth" (Tier C) when their keywords overlap.

The safety net still has veto power: if a role hits a hard filter, the LLM's
"shortlist" is downgraded to "discovered" regardless of its score. Intelligence
proposes; deterministic rules can refuse.

## 4. Three-gate sequential screening

Role fit is necessary but not sufficient. Real rejections happen at company and
product layers. Screening is three gates, evaluated in order (stop at the first
failure) — see [docs/SCREENING_RUBRIC.md](docs/SCREENING_RUBRIC.md):

- **Gate 1 — Role direction** (read the JD body, not the list title; titles get
  cross-wired with sidebar recommendations). Code: `hard_filter_reasons` +
  `classify_archetype`.
- **Gate 2 — Company quality** (founding year, size/funding, work schedule,
  outsourcing/call-center). Deterministic. Code: `company_quality_flags`, fed by
  `browser/cdp_company.mjs`.
- **Gate 3 — Product moat & major fit** (does the product have a defensible
  position? is the role actually adjacent to your background?). A judgment call,
  human-in-the-loop.

Gates 1–2 are deterministic and run by the machine; gate 3 is the human's job.

## 5. One-pass orchestrator + one human touch

`agent/discover.py` front-loads *all* machine work into a single command:
search → ingest → rule pre-filter → read JD → company health → deterministic
gate → emit `_batch_packet.json` of survivors. The human engages exactly once,
on real candidates only. This directly fixes the "approve→sent leak" where
roles looked ready but died at send-time on company/work-condition red flags.

## 6. Inverted-pyramid decision cards

`agent/render_decision_batch.py` renders **conclusion-first** cards: verdict →
company-health line → the one driving reason → the single biggest risk. The goal
is a ~15-second confirm, not a re-analysis. Cards are explicitly marked
`公司未核` when company facts are missing (trust calibration — never imply
verification that didn't happen).

## 7. Canonical ledger + funnel learning

`data/applications.csv` is the single source of truth for every role's
lifecycle. A disciplined status taxonomy (discovered → shortlisted → approved →
applied → replied → interview, plus skipped/rejected/expired/risk_blocked/...)
makes the funnel measurable. `agent/weekly_review.py` turns outcomes into a
review so the strategy learns which keywords convert and which false positives
to exclude next week (by editing config, not code).

## 8. Anti-risk-control browser isolation

All BOSS interaction goes through a **dedicated, isolated Chrome for Testing** on
CDP port 9222 with its own profile — a real logged-in session, never headless
automation (which trips bot-detection), and never your daily Chrome (which would
get its focus hijacked). Human-paced waits and randomized delays throughout. See
[docs/SAFETY.md](docs/SAFETY.md).

## 9. Manual-send safety rail (the hard boundary)

Discovery, scoring, drafting, tracking: automated. Sending greetings, applying,
solving captchas, anything that changes platform state: **always manual**. The
agent stages tabs (`browser/cdp_open.mjs`) and copy, but a human clicks send.
This is non-negotiable and is the reason the system stays usable without getting
the account banned.

---

## Module map

```
config/profile.yaml        # (gitignored) the one personalization file
config/profile.example.yaml# documented template / generic persona

agent/
  config.py                # load profile.yaml, resolve paths, lexicon helpers
  rules.py                 # archetype classification + band scoring + hard filters  (the engine)
  ledger.py                # data/applications.csv read/write, canonical keys
  ingest.py                # search-page cards -> ledger (discovered)
  discover.py              # one-pass orchestrator (search→ingest→prefilter→JD→company→gate)
  llm_eval.py              # apply in-session LLM JD judgments to the ledger
  decide.py                # approve/skip by queue number
  greetings.py             # config-template greeting drafts
  render_decision_batch.py # inverted-pyramid decision cards
  render_send_queue.py     # ordered manual-send checklist + open-urls
  render_dashboard.py      # Dashboard.md + Approval Queue.md
  weekly_review.py         # funnel + outcomes
  healthcheck.py           # preflight: compile, ledger integrity, secret leaks, views

browser/
  launch_chrome.sh         # start the isolated Chrome for Testing on CDP 9222
  cdp_search.mjs           # extract job cards from a search URL
  cdp_detail.mjs           # read JD bodies (incremental, resumable)
  cdp_company.mjs          # read 工商信息 (founding/size/funding) -> company_facts.json
  cdp_open.mjs             # open approved roles as tabs for MANUAL sending

data/                      # (gitignored) ledger + caches + greetings + reports inputs
```

## Why BOSS-specific, and how to port

The BOSS-specific parts are isolated to `browser/*.mjs` (DOM selectors, the
`/job_detail/` URL shape, the private-use-area salary digit encoding decoded in
`rules.decode_boss_digits`) and a few city codes in config. The scoring engine,
ledger, screening gates and workflow are platform-agnostic. To target another
platform, reimplement the four `browser/*.mjs` extractors to emit the same JSON
shapes; the rest is unchanged.
