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

# ── 4. Create data directories ───────────────────────────────────
mkdir -p data/db data/stories data/sfx_cache
echo "Data directories ready (data/db, data/stories, data/sfx_cache)."

# ── 5. Build and start the container ─────────────────────────────
echo
echo "Building and starting Voice In The Dark..."
$COMPOSE up -d --build

echo
echo "Container is running. Waiting for startup..."
sleep 3

# ── 6. Create admin account ──────────────────────────────────────
echo
echo "── Create your admin account ──"
read -p "  Admin username: " ADMIN_USER
read -sp "  Admin password: " ADMIN_PASS
echo

$COMPOSE exec -T voice-to-the-dark python -m app.create_user "$ADMIN_USER" "$ADMIN_PASS" --admin
echo

# ── 7. Optional: Cloudflare Tunnel for remote access ─────────────
echo
echo "── Remote Access (optional) ──"
echo "Want to allow access from outside your home network?"
echo "This uses a free Cloudflare Tunnel — no port forwarding needed."
echo "See SETUP_GUIDE.md for how to get a tunnel token."
echo
TUNNEL_ENABLED=""
read -p "  Set up Cloudflare Tunnel now? (y/N): " SETUP_TUNNEL
if [[ "${SETUP_TUNNEL:-}" =~ ^[Yy]$ ]]; then
    read -p "  Paste your Cloudflare Tunnel token: " TUNNEL_TOKEN
    if [ -n "$TUNNEL_TOKEN" ]; then
        if grep -q "CLOUDFLARE_TUNNEL_TOKEN" .env 2>/dev/null; then
            sed -i "s|.*CLOUDFLARE_TUNNEL_TOKEN.*|CLOUDFLARE_TUNNEL_TOKEN=$TUNNEL_TOKEN|" .env
        else
            echo "" >> .env
            echo "CLOUDFLARE_TUNNEL_TOKEN=$TUNNEL_TOKEN" >> .env
        fi
        echo "Tunnel token saved. Starting tunnel..."
        $COMPOSE --profile tunnel up -d
        TUNNEL_ENABLED=true
    fi
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
if [ "${TUNNEL_ENABLED:-}" = "true" ]; then
echo "  Remote access:      via your Cloudflare Tunnel URL"
echo "                      (check your Cloudflare dashboard)"
fi
echo
echo "  Admin account:      $ADMIN_USER"
echo
echo "  Data stored in:     ./data/"
echo "  Logs:               docker compose logs -f"
echo "  Stop:               docker compose down"
echo "  Restart:            docker compose restart"
if [ "${TUNNEL_ENABLED:-}" = "true" ]; then
echo
echo "  Tunnel logs:        docker compose --profile tunnel logs cloudflared"
echo "  Restart w/ tunnel:  docker compose --profile tunnel up -d"
echo "  Stop tunnel only:   docker compose --profile tunnel stop cloudflared"
fi
echo
echo "  The app auto-starts on reboot."
echo "========================================"
