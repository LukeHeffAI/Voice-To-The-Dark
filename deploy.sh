#!/usr/bin/env bash
set -euo pipefail

# ─── Voice In The Dark — Deployment Script ────────────────────────
# Run this once on your Linux server to set everything up.
# After that, the app auto-starts on reboot via Docker.

COMPOSE="docker compose"

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
    echo
    echo "*** IMPORTANT: Edit .env and add your API keys before continuing! ***"
    echo "  Required keys: ELEVENLABS_API_KEY, ANTHROPIC_API_KEY"
    echo
    read -p "Press Enter after you've edited .env (or Ctrl+C to abort)..."
fi

# ── 3. Generate JWT secret if still default ──────────────────────
if grep -q "change_me_to_a_random_secret" .env 2>/dev/null; then
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    sed -i "s/change_me_to_a_random_secret/$JWT_SECRET/" .env
    echo "Generated JWT secret key."
fi

# ── 4. Add ALLOWED_HOSTS if not in .env ──────────────────────────
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$LAN_IP" ]; then
    LAN_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')
fi
if [ -z "$LAN_IP" ]; then
    LAN_IP=""
fi

if ! grep -q "ALLOWED_HOSTS" .env 2>/dev/null; then
    if [ -n "$LAN_IP" ]; then
        echo "ALLOWED_HOSTS=localhost,127.0.0.1,${LAN_IP}" >> .env
    else
        echo "ALLOWED_HOSTS=localhost,127.0.0.1" >> .env
    fi
    echo "Added ALLOWED_HOSTS to .env."
fi

# ── 5. Create data directories ───────────────────────────────────
mkdir -p data/db data/stories data/sfx_cache data/voice_previews data/segment_cache data/reddit_cache
echo "Data directories ready."

# ── 6. Build and start the container ─────────────────────────────
echo
echo "Building and starting Voice In The Dark..."
$COMPOSE up -d --build

echo
echo "Container is running. Waiting for startup..."
sleep 5

# ── 7. Migrate v1 data (if legacy database exists) ───────────────
if [ -f data/db/stories.db ] || [ -f data/db/horror_narrator.db ]; then
    echo
    echo "Legacy v1 database detected."
    read -p "  Migrate data from v1? (y/N): " MIGRATE
    if [[ "${MIGRATE:-}" =~ ^[Yy]$ ]]; then
        V1_DB="data/db/stories.db"
        [ -f data/db/horror_narrator.db ] && V1_DB="data/db/horror_narrator.db"
        $COMPOSE exec -T voice-to-the-dark python scripts/migrate_from_v1.py "/app/$V1_DB"
        echo "Data migration complete."
    fi
fi

# ── 8. Create admin account ──────────────────────────────────────
echo
echo "── Create your admin account ──"
read -p "  Admin username: " ADMIN_USER
read -sp "  Admin password: " ADMIN_PASS
echo

$COMPOSE exec -T voice-to-the-dark python manage.py createuser "$ADMIN_USER" "$ADMIN_PASS" --admin
echo

# ── 9. Print access info ─────────────────────────────────────────
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
echo "  Admin account:      $ADMIN_USER"
echo
echo "  Data stored in:     ./data/"
echo "  Logs:               docker compose logs -f"
echo "  Stop:               docker compose down"
echo "  Restart:            docker compose restart"
echo "  Remote access:      bash tunnel.sh  (optional, see SETUP_GUIDE.md)"
echo
echo "  The app auto-starts on reboot."
echo "========================================"
