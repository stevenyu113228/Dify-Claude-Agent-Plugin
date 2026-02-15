#!/usr/bin/env bash
set -euo pipefail

# Dify Claude Agent Plugin - Quick Setup
# Patches your Dify Docker deployment to support the Claude Agent plugin.
#
# Usage:
#   ./setup.sh /path/to/dify/docker
#
# What it does:
#   1. Copies plugin-daemon.Dockerfile and docker-compose.override.yaml into your Dify docker/ dir
#   2. Sets FORCE_VERIFYING_SIGNATURE=false in .env (required for custom plugins)
#   3. Builds the custom plugin daemon image (adds Node.js + Claude CLI)
#   4. Restarts the plugin daemon container

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIFY_DOCKER_DIR="${1:-}"

if [ -z "$DIFY_DOCKER_DIR" ]; then
    echo "Usage: $0 /path/to/dify/docker"
    echo ""
    echo "Example:"
    echo "  $0 ~/dify/docker"
    exit 1
fi

if [ ! -f "$DIFY_DOCKER_DIR/docker-compose.yaml" ]; then
    echo "Error: docker-compose.yaml not found in $DIFY_DOCKER_DIR"
    echo "Make sure you point to the Dify docker/ directory."
    exit 1
fi

echo "==> Copying files to $DIFY_DOCKER_DIR ..."
cp "$SCRIPT_DIR/plugin-daemon.Dockerfile" "$DIFY_DOCKER_DIR/"
cp "$SCRIPT_DIR/docker-compose.override.yaml" "$DIFY_DOCKER_DIR/"

echo "==> Disabling plugin signature verification ..."
if [ -f "$DIFY_DOCKER_DIR/.env" ]; then
    if grep -q "FORCE_VERIFYING_SIGNATURE" "$DIFY_DOCKER_DIR/.env"; then
        sed -i.bak 's/FORCE_VERIFYING_SIGNATURE=true/FORCE_VERIFYING_SIGNATURE=false/' "$DIFY_DOCKER_DIR/.env"
    else
        echo "FORCE_VERIFYING_SIGNATURE=false" >> "$DIFY_DOCKER_DIR/.env"
    fi
else
    echo "FORCE_VERIFYING_SIGNATURE=false" > "$DIFY_DOCKER_DIR/.env"
fi
echo "    FORCE_VERIFYING_SIGNATURE=false"

echo "==> Building custom plugin daemon image ..."
cd "$DIFY_DOCKER_DIR"
docker compose build plugin_daemon

echo "==> Restarting plugin daemon ..."
docker compose up -d plugin_daemon

echo ""
echo "==> Verifying installation ..."
CONTAINER=$(docker compose ps -q plugin_daemon)
NODE_VER=$(docker exec "$CONTAINER" node --version 2>/dev/null || echo "NOT FOUND")
CLAUDE_VER=$(docker exec "$CONTAINER" claude --version 2>/dev/null || echo "NOT FOUND")
WRAPPER=$(docker exec "$CONTAINER" which claude-wrapper 2>/dev/null || echo "NOT FOUND")

echo "    Node.js:        $NODE_VER"
echo "    Claude CLI:     $CLAUDE_VER"
echo "    claude-wrapper: $WRAPPER"
echo ""
echo "Done! Next steps:"
echo "  1. Open Dify UI -> Plugins -> Install Plugin -> Local Upload"
echo "  2. Upload dify-claude-agent.difypkg"
echo "  3. Configure your Anthropic API Key or OAuth Token"
echo "  4. Add 'Claude Agent' tool to your workflow"
