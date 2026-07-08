#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker &>/dev/null; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  echo "Docker installed. Re-login or run: newgrp docker"
fi

if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
  echo "Installing Docker Compose..."
  sudo apt-get update && sudo apt-get install -y docker-compose-plugin
fi

echo "Setting up environment variables"
ENV_FILE=.env
[ -f "$ENV_FILE" ] && echo ".env exists, edit it to update values" && cat "$ENV_FILE" && echo ""

read -p "GROQ_API_KEY: " GROQ_API_KEY
read -sp "JWT_SECRET (press enter to generate): " JWT_SECRET_INPUT
echo ""
JWT_SECRET="${JWT_SECRET_INPUT:-$(openssl rand -hex 32)}"
read -p "GOOGLE_CLIENT_ID: " GOOGLE_CLIENT_ID
read -p "GITHUB_TOKEN: " GITHUB_TOKEN

cat > "$ENV_FILE" <<EOF
GROQ_API_KEY=$GROQ_API_KEY
JWT_SECRET=$JWT_SECRET
GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID
GITHUB_TOKEN=$GITHUB_TOKEN
EOF

read -p "Domain name (leave blank for HTTP-only IP access): " DOMAIN
if [ -n "$DOMAIN" ]; then
  cat > Caddyfile <<CADDY
$DOMAIN {
    reverse_proxy app:8080
}

:80 {
    redir https://$DOMAIN{uri}
}
CADDY
  echo "Caddy configured for $DOMAIN (auto HTTPS via Let's Encrypt)"
fi

echo "Starting services..."
docker compose up -d --build

echo ""
echo "=== Done ==="
IP=$(curl -s ifconfig.me 2>/dev/null || echo "unknown")
if [ -n "${DOMAIN:-}" ]; then
  echo "API URL: https://$DOMAIN"
else
  echo "API URL: http://$IP"
fi
echo "Health:   http://$IP/health"
echo ""
echo "To set a budget alert, visit: https://cloud.oracle.com/budget"
