# Contributing

Thanks for your interest. A few principles keep this project coherent:

1. **Personalization is config, not code.** Anything candidate-specific
   (keywords, preferences, story, thresholds) belongs in `config/profile.yaml`
   and its documented template, never hardcoded in `agent/` or `browser/`.
2. **The manual-send rail is non-negotiable.** PRs that add auto-greeting,
   auto-apply, bulk outreach, or captcha/risk-control bypass will be declined.
   See [docs/SAFETY.md](docs/SAFETY.md).
3. **Keep the engine platform-agnostic.** BOSS-specific details live in
   `browser/*.mjs` and a few config values. New platform support = new
   extractors emitting the same JSON shapes; don't leak platform details into
   `agent/rules.py`.
4. **Never commit user data.** `config/profile.yaml`, `data/*`, and generated
   views are gitignored. Double-check `git status` before pushing.

## Dev setup

```bash
pip install -r requirements.txt
cp config/profile.example.yaml config/profile.yaml
cp examples/sample_search_page.json data/current_page.json
python3 -m agent.ingest && python3 -m agent.render_dashboard
python3 -m agent.healthcheck
```

`healthcheck` compiles every script, checks ledger integrity, scans for leaked
auth/cookie files, and re-renders the views. Run it before opening a PR.

## Scope of good contributions

- New `browser/*.mjs` extractors (other platforms, robustness to DOM changes).
- More archetypes / lexicon presets for different career tracks (as config).
- Better renderers, funnel analytics, and tests.
