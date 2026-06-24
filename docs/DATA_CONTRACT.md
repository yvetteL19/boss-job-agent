# Data Contract

Two layers, kept strictly separate so the workflow can improve without ever
touching — or leaking — your private record.

## User layer (private, gitignored, never overwritten by tool upgrades)

| Path | Purpose |
|---|---|
| `config/profile.yaml` | Your targets, hard filters, scoring weights, greeting templates, lexicon |
| `data/applications.csv` | Canonical ledger: every role's lifecycle (the truth source) |
| `data/current_page.json` | Latest search-card snapshot from the isolated browser |
| `data/_jd_reads.json` | Extracted JD bodies |
| `data/company_facts.json` | Company 工商信息 (founding/size/funding) cache |
| `data/_batch_packet.json` | Orchestrator survivors for human review |
| `data/greetings.json` | `{job_url: greeting}` — the manual-send truth source |
| `data/llm_evals.json` | In-session LLM judgments to apply |
| `reports/*` | Generated weekly reviews and per-JD evaluations |
| `Dashboard.md`, `Approval Queue.md`, `Decision Batch.md`, `Send Queue.md` | Generated operating views |

All of the above are in `.gitignore`. **Nothing in this layer is ever committed.**

## System layer (shared logic, safe to upgrade)

| Path | Purpose |
|---|---|
| `agent/*` | Config loader, scoring engine, ledger, orchestrator, renderers, reviews |
| `browser/*` | Isolated-Chrome CDP extractors + launcher |
| `templates/*` | Reusable note templates |
| `config/profile.example.yaml` | Documented config template (generic persona) |
| `docs/*`, `README.md`, `ARCHITECTURE.md` | Documentation |

## Rules

1. Discovery, scoring, JD evaluation, logging, rendering and reviews can be
   automated.
2. Applying, replying, captcha handling, and any account-state-changing action
   require a human (see [SAFETY.md](SAFETY.md)).
3. **New personalization belongs in `config/profile.yaml`, not in scripts.**
   Scripts may *read* the profile; they write only generated outputs and the
   ledger.
4. Search-card imports default to `discovered`. Promote to `shortlisted` only
   after hard filters pass and, ideally, JD-body evidence exists.
5. Treat short/failed/hidden JD pages as under-evidenced; do not auto-promote.
6. When a role is risky, stale, unknown, or blocked by verification, preserve
   evidence and stop the batch.
