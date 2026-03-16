#!/usr/bin/env bash
set -euo pipefail

# ─── Voice In The Dark — Deployment Verification ─────────────────
# Checks that the deployed app is responding correctly.
# Usage: bash scripts/verify_deployment.sh [base_url]

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0

check() {
    local name="$1"
    local url="$2"
    local expected="$3"

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")

    if echo "$expected" | grep -q "$HTTP_CODE"; then
        echo "  ✓ $name ($HTTP_CODE)"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $name (got $HTTP_CODE, expected $expected)"
        FAIL=$((FAIL + 1))
    fi
}

echo "Verifying deployment at $BASE_URL..."
echo

check "API root"          "$BASE_URL/api/"        "200"
check "SPA frontend"      "$BASE_URL/"            "200"
check "SPA catch-all"     "$BASE_URL/story/1"     "200"
check "Login route"       "$BASE_URL/login"        "200"
check "Stories API"       "$BASE_URL/api/stories/" "200|401"
check "Auth API"          "$BASE_URL/api/auth/me"  "401"
check "Django admin"      "$BASE_URL/admin/"       "200|302"

echo
echo "Results: $PASS passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
