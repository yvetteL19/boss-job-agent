# Safety & platform-risk model

This system is built around one hard constraint: **do not get the account
risk-controlled (封号), and never automate the irreversible step (sending).**
Everything below follows from that.

## The two iron rules

1. **Sending is always manual.** The agent discovers, reads, scores, drafts and
   tracks. It never auto-sends greetings, auto-applies, or solves captchas. It
   stages tabs and copy; a human clicks send.
2. **Headless automation trips risk control.** Headless browser automation against
   BOSS reliably triggers bot-detection (account risk / code36). So all reads go
   through a real, logged-in, **non-headless** session, paced like a human.

## Browser isolation (why a separate Chrome)

All BOSS interaction uses a **dedicated, isolated Chrome for Testing** on CDP
port 9222 with its own user profile (`~/.boss-agent-cdp-profile` by default):

- **Separate from your daily Chrome.** Driving your daily browser via automation
  steals focus every time a tab opens, making it unusable; the isolated browser
  is a different process/window that can stay backgrounded.
- **Real logged-in session.** You scan the QR once; cookies persist in the
  isolated profile. Re-scan only when the session expires.
- **CDP navigation, human pace.** Scripts navigate via the DevTools protocol with
  multi-second waits and randomized delays. No headless, no patchright.

Regular Chrome reuses an existing process and ignores `--remote-debugging-port`,
so a dedicated Chrome for Testing binary is required for a reliable debug port.
See `browser/launch_chrome.sh`.

### Passive vs. active reads

- **Active discovery / multi-page reads** (search, JD bodies, company pages):
  isolated Chrome for Testing on 9222, driven by `browser/*.mjs`.
- **Passive read of a tab you already have open** (e.g. checking your chat list
  for progress): can use your daily Chrome *read-only* with "Allow JavaScript
  from Apple Events", precisely because it does **not** open or navigate tabs.

## Pacing guidance

- Keep batches small (`--top 12` is plenty). Widen the funnel across keywords/
  cities rather than hammering one query deep.
- The scripts already sleep 3–8s between page reads with jitter. Don't remove
  these waits.
- Stop the batch immediately on any captcha, risk warning, repeated unknowns, or
  login instability. Wait out the cooldown; don't push.

## What this project deliberately does NOT do

- No auto-greeting / auto-apply / bulk outreach.
- No captcha or verification bypass.
- No detection-evasion tooling beyond using a real logged-in session at human
  pace.
- No scraping of other users' private data.

## Your responsibility

Using automation against a platform may conflict with its Terms of Service. This
tool is for assisting your **own** job search at low volume. Respect the
platform's rules, keep volume sane, and accept the risk yourself. The authors
provide no warranty (see LICENSE).
