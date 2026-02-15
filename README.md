# Dify Claude Agent Plugin

A Dify plugin that integrates [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview),
enabling autonomous Claude Agents as tool nodes in Dify workflows.

## Prerequisites

- Dify 1.9+ with Plugin support enabled
- Anthropic API Key or Claude Code OAuth Token

## Installation (Docker Deployment)

If your Dify is running via Docker Compose, the plugin daemon container needs Node.js and Claude CLI installed. Follow these steps:

### Step 1: Create Custom Plugin Daemon Dockerfile

Create `plugin-daemon.Dockerfile` in your Dify `docker/` directory:

```dockerfile
FROM langgenius/dify-plugin-daemon:0.5.3-local

# Install Node.js 22.x (LTS)
RUN apt-get update && \
    apt-get install -y ca-certificates curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo 'deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main' > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Claude CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Verify installations
RUN node --version && npm --version && claude --version
```

### Step 2: Modify docker-compose.yaml

Find the `plugin_daemon` service and replace the `image:` line with a `build:` block:

```yaml
  plugin_daemon:
    # Replace this:
    # image: langgenius/dify-plugin-daemon:0.5.3-local
    # With this:
    build:
      context: .
      dockerfile: plugin-daemon.Dockerfile
    image: dify-plugin-daemon-claude:0.5.3
    restart: always
    environment:
      # ... (keep all existing environment variables)
```

### Step 3: Disable Plugin Signature Verification

Custom plugins are not signed by the Dify marketplace. You must disable signature verification.

In your `docker/.env` file, set:

```
FORCE_VERIFYING_SIGNATURE=false
```

### Step 4: Build and Restart

```bash
cd /path/to/dify/docker
docker compose build plugin_daemon
docker compose up -d plugin_daemon
```

Verify the container has Node.js and Claude CLI:

```bash
docker exec <plugin_daemon_container> node --version   # v22.x
docker exec <plugin_daemon_container> claude --version  # 2.x
```

### Step 5: Install the Plugin

1. Package the plugin (requires [Dify CLI](https://github.com/langgenius/dify-plugin-daemon/releases)):
   ```bash
   # Install Dify CLI (macOS)
   brew tap langgenius/dify && brew install dify
   # Or download binary directly from GitHub releases

   # Package
   dify plugin package ./dify-claude-agent
   ```
2. Open Dify UI → **Plugins** → **Install Plugin** → **Local Upload**
3. Upload `dify-claude-agent.difypkg`
4. Configure credentials:
   - **Anthropic API Key** (`sk-ant-...`) or
   - **Claude Code OAuth Token**

## Usage

### Basic Agent Node

1. Add "Claude Agent" tool to your Dify workflow
2. Configure model, allowed tools, and budget
3. Connect the prompt input
4. Connect output to downstream nodes

### Chaining Agents

Connect multiple Claude Agent nodes in sequence.
Each node receives the previous agent's output as context:

```
[Start] -> [Agent: Research] -> [Agent: Summarize] -> [Agent: Write] -> [End]
```

### Subagent Configuration

Enable in-node delegation by providing a JSON config:

```json
{
  "researcher": {
    "description": "Expert at finding information",
    "prompt": "Research the given topic thoroughly",
    "tools": ["Read", "WebSearch", "WebFetch"],
    "model": "haiku"
  }
}
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| prompt | string | (required) | Task for the agent |
| model | select | claude-sonnet-4-5 | Claude model to use |
| system_prompt | string | - | Custom system prompt |
| permission_mode | select | bypassPermissions | Agent permission level |
| max_turns | number | 10 | Max agent turns |
| max_budget_usd | number | 1.0 | Spending limit (USD) |
| allowed_tools | string | Read,Glob,Grep,WebSearch,WebFetch | Tools the agent can use |
| subagent_config | string | - | JSON subagent definitions |

### Available Tools

`Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, `WebSearch`, `WebFetch`, `Task`, `NotebookEdit`, `AskUserQuestion`, `TodoWrite`

## Output

The tool returns:

- **Text**: The agent's final text output (streamed in real-time)
- **JSON**: Structured metadata
  ```json
  {
    "result": "agent's text output",
    "cost_usd": 0.05,
    "duration_ms": 12345,
    "is_error": false,
    "session_id": "abc-123",
    "num_turns": 5
  }
  ```

## Development

### From Source (Debug Mode)

```bash
cd dify-claude-agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Dify debug credentials
python -m main
```

### Run Tests

```bash
cd dify-claude-agent
python -m pytest tests/ -v
```

## License

MIT
