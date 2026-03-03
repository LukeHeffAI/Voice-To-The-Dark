#!/usr/bin/env bash
set -euo pipefail

# ─── Cloudflare Tunnel Setup ─────────────────────────────────────
# Run this to enable or disable remote access via Cloudflare Tunnel.
# See SETUP_GUIDE.md for how to get a tunnel token.

COMPOSE="docker compose"

show_help() {
    echo "Usage: bash tunnel.sh [enable|disable|status]"
    echo
    echo "  enable   — Add your tunnel token and start the tunnel"
    echo "  disable  — Stop the tunnel and remove the token"
    echo "  status   — Show whether the tunnel is running"
    echo
    echo "  (no args) — Interactive setup"
}

enable_tunnel() {
    if [ -z "${1:-}" ]; then
        read -p "  Paste your Cloudflare Tunnel token: " TOKEN
    else
        TOKEN="$1"
    fi

    if [ -z "$TOKEN" ]; then
        echo "No token provided. Aborting."
        exit 1
    fi

    # Save token to .env
    if grep -q "CLOUDFLARE_TUNNEL_TOKEN" .env 2>/dev/null; then
        sed -i "s|.*CLOUDFLARE_TUNNEL_TOKEN.*|CLOUDFLARE_TUNNEL_TOKEN=$TOKEN|" .env
    else
        echo "" >> .env
        echo "CLOUDFLARE_TUNNEL_TOKEN=$TOKEN" >> .env
    fi

    echo "Tunnel token saved. Starting tunnel..."
    $COMPOSE --profile tunnel up -d
    echo
    echo "Tunnel is running. Check your Cloudflare dashboard for the public URL."
    echo "  Logs:  docker compose --profile tunnel logs -f cloudflared"
}

disable_tunnel() {
    echo "Stopping tunnel..."
    $COMPOSE --profile tunnel stop cloudflared 2>/dev/null || true

    # Comment out the token in .env
    if grep -q "^CLOUDFLARE_TUNNEL_TOKEN" .env 2>/dev/null; then
        sed -i "s|^CLOUDFLARE_TUNNEL_TOKEN|# CLOUDFLARE_TUNNEL_TOKEN|" .env
        echo "Tunnel stopped and token commented out in .env."
    else
        echo "Tunnel stopped."
    fi
}

show_status() {
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "cloudflared-tunnel"; then
        echo "Tunnel is RUNNING."
        echo
        docker ps --filter name=cloudflared-tunnel --format "  Container: {{.Names}}\n  Status:    {{.Status}}"
    else
        echo "Tunnel is NOT running."
    fi
    echo
    if grep -q "^CLOUDFLARE_TUNNEL_TOKEN" .env 2>/dev/null; then
        echo "Token is configured in .env."
    else
        echo "No token configured in .env."
    fi
}

case "${1:-}" in
    enable)
        enable_tunnel "${2:-}"
        ;;
    disable)
        disable_tunnel
        ;;
    status)
        show_status
        ;;
    -h|--help|help)
        show_help
        ;;
    *)
        # Interactive mode
        echo "========================================"
        echo "  Cloudflare Tunnel Setup"
        echo "========================================"
        echo
        show_status
        echo
        echo "This uses a free Cloudflare Tunnel for remote access."
        echo "No port forwarding needed — see SETUP_GUIDE.md for details."
        echo
        read -p "  Enable tunnel? (y/N): " CHOICE
        if [[ "${CHOICE:-}" =~ ^[Yy]$ ]]; then
            enable_tunnel
        else
            echo "No changes made."
        fi
        ;;
esac
