#!/usr/bin/env bash
# Post-deploy smoke test. Hits a few critical endpoints, fails on non-2xx.
# Usage: BASE_URL=https://mooviogo.example.com ./scripts/smoke_test.sh

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
TIMEOUT="${SMOKE_TIMEOUT:-10}"

fail() {
    echo "[smoke] FAIL: $1" >&2
    exit 1
}

check() {
    local path="$1"
    local expected="${2:-200}"
    local status
    status=$(curl -fsS -o /dev/null -w "%{http_code}" -m "$TIMEOUT" "$BASE_URL$path" || echo "000")
    if [[ "$status" != "$expected" ]]; then
        fail "$path returned $status (expected $expected)"
    fi
    echo "[smoke] OK  $path → $status"
}

echo "[smoke] BASE_URL=$BASE_URL"
check /health/             200
check /health/ready/       200
check /                    200
check /sorties/            200
check /evenements/         200
check /robots.txt          200
check /sitemap.xml         200
check /login               200
check /signup              200

echo "[smoke] all good ✓"
