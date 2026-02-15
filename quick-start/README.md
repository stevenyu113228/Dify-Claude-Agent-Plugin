# Quick Start - Dify Claude Agent Plugin

One-script setup to patch your Dify Docker deployment for the Claude Agent plugin.

## What's Included

| File | Purpose |
|------|---------|
| `setup.sh` | Automated setup script (does everything below) |
| `plugin-daemon.Dockerfile` | Custom image: adds Node.js 22 + Claude CLI + gosu wrapper |
| `docker-compose.override.yaml` | Override file that replaces the plugin daemon image with custom build |

## Automated Setup

```bash
./setup.sh /path/to/dify/docker
```

The script will:
1. Copy `plugin-daemon.Dockerfile` and `docker-compose.override.yaml` into your Dify `docker/` directory
2. Set `FORCE_VERIFYING_SIGNATURE=false` in `.env` (required for custom plugins)
3. Build the custom plugin daemon image
4. Restart the plugin daemon container
5. Verify Node.js and Claude CLI are available

## Manual Setup

If you prefer to do it step by step:

```bash
# 1. Copy files
cp plugin-daemon.Dockerfile /path/to/dify/docker/
cp docker-compose.override.yaml /path/to/dify/docker/

# 2. Disable signature verification
# Edit /path/to/dify/docker/.env:
FORCE_VERIFYING_SIGNATURE=false

# 3. Build and restart
cd /path/to/dify/docker
docker compose build plugin_daemon
docker compose up -d plugin_daemon

# 4. Verify
docker exec $(docker compose ps -q plugin_daemon) node --version
docker exec $(docker compose ps -q plugin_daemon) claude --version
docker exec $(docker compose ps -q plugin_daemon) which claude-wrapper
```

## Install the Plugin

After setup completes:

1. Open Dify UI -> **Plugins** -> **Install Plugin** -> **Local Upload**
2. Upload `dify-claude-agent.difypkg` (in the project root)
3. Configure your **Anthropic API Key** or **Claude Code OAuth Token**
4. Add **Claude Agent** tool to your workflow

## Why a Custom Image?

The Claude Agent SDK spawns the Claude CLI (`claude`) as a subprocess. The stock Dify plugin daemon image doesn't include Node.js or the Claude CLI. Additionally:

- The plugin daemon runs as **root** inside Docker
- Claude CLI **refuses** `--dangerously-skip-permissions` when running as root (security measure)
- The custom image adds a `claude-wrapper` script that uses `gosu` to drop to a non-root user (`claude-runner`) before executing the CLI

## Reverting

To go back to the stock plugin daemon:

```bash
cd /path/to/dify/docker
rm plugin-daemon.Dockerfile docker-compose.override.yaml
docker compose up -d plugin_daemon
```
