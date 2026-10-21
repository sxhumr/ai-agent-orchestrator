#!/usr/bin/env bash
# Regenerate the README screenshots and demo GIF in docs/media/ from seeded demo data.
# Needs uv, npm (with `npm ci` done in frontend/) and Playwright's Chromium
# (`cd frontend && npx playwright install chromium`). Makes no Claude Code calls.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_port="${API_PORT:-8799}"
gui_port="${GUI_PORT:-3199}"
work="$(mktemp -d)"
pids=()

# Each server runs in its own process group (setsid), so cleanup stops the real
# server processes too, not just the npx/uv wrappers that started them.
cleanup() {
  for pid in "${pids[@]}"; do kill -- "-$pid" 2>/dev/null || true; done
  rm -rf "$work"
}
trap cleanup EXIT

wait_for() {
  for _ in $(seq 1 120); do
    curl -fsS -o /dev/null "$1" && return 0
    sleep 0.5
  done
  echo "timed out waiting for $1" >&2
  return 1
}

for port in "$api_port" "$gui_port"; do
  if curl -s -o /dev/null "http://127.0.0.1:$port/"; then
    echo "port $port is already in use; set API_PORT or GUI_PORT" >&2
    exit 1
  fi
done

cd "$repo"
uv run --project backend python scripts/seed_demo.py --db "$work/forgeflow.db" --root "$work"

setsid uv run --project backend forgeflow --db "$work/forgeflow.db" serve --port "$api_port" \
  --gui-origin "http://localhost:$gui_port" >"$work/api.log" 2>&1 &
pids+=($!)

# A production build, so no development overlay appears in the screenshots.
(cd frontend && NEXT_PUBLIC_API_URL="http://127.0.0.1:$api_port" npx next build >"$work/build.log" 2>&1)
(cd frontend && exec setsid npx next start -p "$gui_port" >"$work/gui.log" 2>&1) &
pids+=($!)

wait_for "http://127.0.0.1:$api_port/api/health"
wait_for "http://localhost:$gui_port/"

mkdir -p docs/media
output="$(node scripts/capture-media.mjs "http://localhost:$gui_port" docs/media "$work/frames")"
echo "$output" | grep -v '^{'
durations="$(echo "$output" | grep '^{' | python3 -c 'import json,sys; print(*json.load(sys.stdin)["durations"])')"
# shellcheck disable=SC2086
uv run --with pillow python scripts/make_gif.py "$work/frames" docs/media/demo.gif $durations
