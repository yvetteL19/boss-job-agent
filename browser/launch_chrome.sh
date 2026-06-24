#!/usr/bin/env bash
# Launch an ISOLATED Chrome for Testing with remote debugging on port 9222.
# This is a separate browser/profile from your daily Chrome (see docs/SAFETY.md):
#   - it never steals focus from your daily browsing,
#   - CDP navigation drives only this window,
#   - you log in once via QR and keep it backgrounded; re-scan only on expiry.
#
# Why Chrome for Testing (not your regular Chrome): regular Chrome reuses an
# existing process and ignores --remote-debugging-port. A dedicated binary +
# dedicated profile keeps the debugging port reliably open.
#
# 1) Install Chrome for Testing once:
#      npx @puppeteer/browsers install chrome@stable
#    (note the printed path to the chrome binary)
# 2) Set CHROME_BIN to that path (or edit the default below), then run this.
#
# Usage:  CHROME_BIN="/path/to/chrome" bash browser/launch_chrome.sh

set -euo pipefail

PORT="${BOSS_CDP_PORT:-9222}"
PROFILE="${BOSS_CDP_PROFILE:-$HOME/.boss-agent-cdp-profile}"
CHROME_BIN="${CHROME_BIN:-/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing}"

if [[ ! -x "$CHROME_BIN" ]]; then
  echo "Chrome for Testing not found at: $CHROME_BIN" >&2
  echo "Install it:  npx @puppeteer/browsers install chrome@stable" >&2
  echo "Then re-run with:  CHROME_BIN=\"/path/to/chrome\" bash browser/launch_chrome.sh" >&2
  exit 1
fi

mkdir -p "$PROFILE"
echo "Launching isolated Chrome for Testing on CDP port $PORT (profile: $PROFILE)"
echo "Log in to https://www.zhipin.com once via QR, then keep this window backgrounded."
exec "$CHROME_BIN" \
  --remote-debugging-port="$PORT" \
  --user-data-dir="$PROFILE" \
  --no-first-run --no-default-browser-check \
  "https://www.zhipin.com/web/geek/jobs"
