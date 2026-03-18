#!/usr/bin/env bash
set -euo pipefail

# ─── Voice In The Dark — Deployment Script ────────────────────────
# Run this once on your Linux server to set everything up.
# After that, the app auto-starts on reboot via Docker.
#
# Usage:
#   bash deploy.sh            Interactive mode (prompts for input)
#   bash deploy.sh --auto     Unattended mode (uses env vars, no prompts)
#   bash deploy.sh --help     Show this help message
#
# In --auto mode, the following environment variables are used:
#   ELEVENLABS_API_KEY    (required if .env doesn't exist)
#   ANTHROPIC_API_KEY     (required if .env doesn't exist)
#   ADMIN_USER            (optional — creates admin account if set)
#   ADMIN_PASS            (optional — required if ADMIN_USER is set)

COMPOSE="docker compose"
AUTO_MODE=false

# ── Parse arguments ────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --auto)
            AUTO_MODE=true
            ;;
        --help|-h)
            head -n 17 "$0" | tail -n 14 | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: bash deploy.sh [--auto] [--help]"
            exit 1
            ;;
    esac
done

echo "========================================"
echo "  Voice In The Dark — Deployment Setup"
echo "========================================"
echo

# ── 1. Check prerequisites ────────────────────────────────────────
for cmd in docker; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: '$cmd' is not installed. Install Docker first:"
        echo "  https://docs.docker.com/engine/install/"
        exit 1
    fi
done

# Check docker compose (v2 plugin)
if ! docker compose version &>/dev/null; then
    echo "Error: 'docker compose' (v2) not found."
    echo "Install the Docker Compose plugin: https://docs.docker.com/compose/install/"
    exit 1
fi

# ── 2. Set up .env file ──────────────────────────────────────────
if [ ! -f .env ]; then
    echo "No .env file found — creating from .env.example..."
    cp .env.example .env

    if $AUTO_MODE; then
        # In auto mode, inject API keys from environment variables
        if [ -n "${ELEVENLABS_API_KEY:-}" ]; then
            python3 -c "
import re, sys
key = sys.argv[1]
with open('.env') as f: content = f.read()
content = re.sub(r'^ELEVENLABS_API_KEY=.*$', lambda m: 'ELEVENLABS_API_KEY=' + key, content, flags=re.MULTILINE)
with open('.env', 'w') as f: f.write(content)
" "$ELEVENLABS_API_KEY"
        fi
        if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
            python3 -c "
import re, sys
key = sys.argv[1]
with open('.env') as f: content = f.read()
content = re.sub(r'^ANTHROPIC_API_KEY=.*$', lambda m: 'ANTHROPIC_API_KEY=' + key, content, flags=re.MULTILINE)
with open('.env', 'w') as f: f.write(content)
" "$ANTHROPIC_API_KEY"
        fi
        echo "API keys configured from environment variables."
    else
        echo
        echo "*** IMPORTANT: Edit .env and add your API keys before continuing! ***"
        echo "  Required keys: ELEVENLABS_API_KEY, ANTHROPIC_API_KEY"
        echo
        read -p "Press Enter after you've edited .env (or Ctrl+C to abort)..."
    fi
fi

# ── 3. Generate JWT secret if still default ──────────────────────
if grep -q "change_me_to_a_random_secret" .env 2>/dev/null; then
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    sed -i "s/change_me_to_a_random_secret/$JWT_SECRET/" .env
    echo "Generated JWT secret key."
fi

# ── 4. Create data directories ───────────────────────────────────
mkdir -p data/db data/stories data/sfx_cache data/voice_previews data/segment_cache data/reddit_cache data/tmp
echo "Data directories ready."

# ── 5. Build and start the container ─────────────────────────────
echo
echo "Building and starting Voice In The Dark..."
$COMPOSE up -d --build

echo
echo "Container is running. Waiting for startup..."
MAX_WAIT=60
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS=$($COMPOSE ps --format json 2>/dev/null | python3 -c "
import sys, json
raw = sys.stdin.read().strip()
if not raw:
    print('unknown')
    sys.exit(0)
# Handle both JSON array and newline-delimited JSON objects
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    # Try newline-delimited JSON
    data = [json.loads(line) for line in raw.splitlines() if line.strip()]
if isinstance(data, dict):
    data = [data]
for obj in data:
    if obj.get('Name') == 'voice-to-the-dark' or obj.get('Service') == 'voice-to-the-dark':
        print(obj.get('Health', obj.get('State', '')))
        sys.exit(0)
print('unknown')
" 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "healthy" ]; then
        echo "Application is ready!"
        break
    fi
    sleep 3
    ELAPSED=$((ELAPSED + 3))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "Error: Container did not become healthy within ${MAX_WAIT}s."
    echo "Check logs with: docker compose logs"
    exit 1
fi

# ── 6. Migrate legacy data (if upgrading from v1) ────────────────
if [ -f data/db/horror_narrator.db ]; then
    echo
    echo "── Legacy database detected (horror_narrator.db) ──"
    if $AUTO_MODE; then
        echo "  Auto-migrating data from v1..."
        $COMPOSE exec -T voice-to-the-dark python manage.py migrate_legacy_data
        echo "  Legacy data migrated."
    else
        read -p "  Migrate data from v1? (y/N): " MIGRATE_LEGACY
        if [[ "$MIGRATE_LEGACY" =~ ^[Yy] ]]; then
            $COMPOSE exec -T voice-to-the-dark python manage.py migrate_legacy_data
            echo "  Legacy data migrated."
        fi
    fi
fi

# ── 7. Create admin account ──────────────────────────────────────
if $AUTO_MODE; then
    if [ -n "${ADMIN_USER:-}" ] && [ -n "${ADMIN_PASS:-}" ]; then
        echo
        echo "── Creating admin account ──"
        $COMPOSE exec -T voice-to-the-dark python manage.py createuser "$ADMIN_USER" "$ADMIN_PASS" --admin
        echo "  Admin account '$ADMIN_USER' created."
    fi
else
    echo
    echo "── Create your admin account ──"
    read -p "  Admin username: " ADMIN_USER
    read -sp "  Admin password: " ADMIN_PASS
    echo

    $COMPOSE exec -T voice-to-the-dark python manage.py createuser "$ADMIN_USER" "$ADMIN_PASS" --admin
    echo
fi

# ── 8. Detect LAN IP and print access info ───────────────────────
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$LAN_IP" ]; then
    LAN_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')
fi
if [ -z "$LAN_IP" ]; then
    LAN_IP="<your-server-ip>"
fi

echo
echo "========================================"
echo "  Deployment complete!"
echo "========================================"
echo
echo "  On this machine:    http://localhost:8000"
echo "  On your network:    http://${LAN_IP}:8000"
echo
if [ -n "${ADMIN_USER:-}" ]; then
    echo "  Admin account:      $ADMIN_USER"
    echo
fi
echo "  Data stored in:     ./data/"
echo "  Logs:               docker compose logs -f"
echo "  Stop:               docker compose down"
echo "  Restart:            docker compose restart"
echo "  Remote access:      bash tunnel.sh  (optional, see SETUP_GUIDE.md)"
echo
echo "  The app auto-starts on reboot."
echo "========================================"
