# Dify Claude Agent Plugin

A Dify plugin that integrates [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview),
enabling autonomous Claude Agents as tool nodes in Dify workflows.

## Prerequisites

- Dify 1.9+ with Plugin support enabled
- Node.js 18+ on the Dify host
- Claude CLI: `npm install -g @anthropic-ai/claude-code`
- Anthropic API Key or Claude Code OAuth Token

## Installation

### From Package

1. Download the latest `.difypkg` from Releases
2. Go to Dify > Plugin Management > Upload Plugin
3. Configure your Anthropic API Key or OAuth Token

### From Source (Development)

```bash
cd dify-claude-agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Dify debug credentials
python -m main
```

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

```bash
cd dify-claude-agent
python -m pytest tests/ -v
```

## License

MIT
