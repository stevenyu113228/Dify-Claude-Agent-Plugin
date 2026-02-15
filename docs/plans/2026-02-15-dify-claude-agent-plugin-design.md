# Dify Claude Agent Plugin — Design Document

**Date:** 2026-02-15
**Status:** Approved

## Overview

A Dify plugin that integrates the Claude Agent SDK, enabling users to use autonomous Claude Agents as tool nodes in Dify workflows. Each node runs a configurable Claude Agent that can read files, execute commands, search the web, and more. Agents can be chained via Dify's workflow to pipe results between multiple Claude Agents.

## Architecture Decision

**Approach:** Single monolithic tool plugin (Approach A)
- One `claude_agent` tool with all configuration exposed as form parameters
- Python-only implementation (Dify plugins require Python; Claude Agent SDK supports Python)
- Subagent support within a single node + Dify workflow chaining for multi-agent orchestration

## Plugin Structure

```
dify-claude-agent/
├── manifest.yaml                    # Plugin metadata, permissions
├── requirements.txt                 # Python deps: claude-agent-sdk
├── main.py                          # Entry point (auto-generated)
├── _assets/
│   └── icon.svg                     # Plugin icon (SVG)
├── provider/
│   ├── claude_agent_provider.yaml   # Provider: credentials definition
│   └── claude_agent_provider.py     # Credential validation logic
└── tools/
    ├── claude_agent.yaml            # Tool: parameter definitions
    └── claude_agent.py              # Tool: agent execution logic
```

## Credentials

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `anthropic_api_key` | secret-input | No | Anthropic API key |
| `claude_code_oauth_token` | secret-input | No | Claude Code OAuth token (alternative) |

At least one credential must be provided. Validated at provider level.

## Tool Parameters

### Form parameters (configured before execution)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model` | select | No | `claude-sonnet-4-5-20250929` | Model: opus-4-6, sonnet-4-5, haiku-4-5 |
| `system_prompt` | string | No | — | Custom system prompt |
| `permission_mode` | select | No | `bypassPermissions` | Permission mode for tool use |
| `max_turns` | number | No | 10 | Max agentic turns |
| `max_budget_usd` | number | No | 1.0 | Max budget in USD |
| `allowed_tools` | string | No | `Read,Glob,Grep,WebSearch,WebFetch` | Comma-separated allowed tools |
| `subagent_config` | string | No | — | JSON config for subagents |

### LLM parameters (inferred at runtime)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | Yes | The task/prompt to send to the Claude Agent |

## Output

The tool yields two outputs for downstream nodes:

1. **Text message** — Agent's final text result (streamed with typewriter effect)
2. **JSON message** — Structured data:
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

## Data Flow

```
Dify Workflow Node
  │
  ▼
1. Extract parameters (prompt, model, tools, etc.)
2. Get credentials (api_key or oauth_token)
3. Set auth environment variable
4. Build ClaudeAgentOptions
5. Call query() with async bridging
6. Stream partial text via create_stream_variable_message()
7. Collect final SDKResultMessage
8. Yield text + JSON outputs
9. Restore environment
  │
  ▼
Next Dify Workflow Node
```

## Streaming

Partial agent responses are streamed to the Dify UI in real-time using `create_stream_variable_message("text", partial_text)`. This gives users visibility into the agent's work while it executes.

## Subagent Support

When `subagent_config` is provided as JSON, it's parsed and passed to the Claude Agent SDK's `agents` parameter:

```json
{
  "researcher": {
    "description": "Expert researcher for finding information",
    "prompt": "Research the given topic thoroughly",
    "tools": ["Read", "WebSearch", "WebFetch"],
    "model": "haiku"
  },
  "coder": {
    "description": "Expert coder for writing and editing code",
    "prompt": "Write clean, well-tested code",
    "tools": ["Read", "Write", "Edit", "Bash"],
    "model": "sonnet"
  }
}
```

## Error Handling

| Error Type | Handling |
|------------|----------|
| Missing credentials | `ToolProviderCredentialValidationError` |
| Agent timeout | Yield error text + JSON with `is_error: true` |
| Budget exceeded | Yield partial output + error flag |
| Max turns exceeded | Yield partial output + error flag |
| Network errors | Yield descriptive error message |
| Invalid subagent JSON | Validate before SDK call, yield parse error |

## Async Bridging

The Claude Agent SDK uses async generators (`async for`), but Dify plugin tools use synchronous generators. We bridge this using `asyncio.run()` with an internal async function that collects results.

## Dependencies

- `claude-agent-sdk` — Claude Agent SDK for Python
- `dify_plugin` — Dify Plugin SDK (provided by runtime)

## Testing Strategy

1. **Unit tests:** Mock `query()` to test parameter mapping, error handling, output formatting
2. **Integration:** Dify plugin remote debugging mode against a real Dify instance
3. **Manual:** Install `.difypkg`, create a workflow with chained Claude Agent nodes

## Security Considerations

- API keys stored as `secret-input` (encrypted by Dify)
- Environment variables for auth are set/restored per invocation to avoid leaking between concurrent runs
- `bypassPermissions` is the default since the agent runs in a server context (no human to approve)
- `max_budget_usd` prevents runaway costs
- `max_turns` prevents infinite loops
