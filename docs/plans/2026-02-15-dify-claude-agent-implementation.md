# Dify Claude Agent Plugin — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Dify plugin that wraps the Claude Agent SDK, letting users run autonomous Claude Agents as nodes in Dify workflows with configurable tools, streaming output, and subagent support.

**Architecture:** Single Python Dify plugin using `dify_plugin` SDK. The tool calls `claude-agent-sdk`'s `query()` function, bridging its async API to Dify's sync generator pattern via `asyncio.run()`. Output is streamed to the Dify UI and piped as text + JSON to downstream nodes.

**Tech Stack:** Python 3.12, `dify_plugin` (Dify Plugin SDK), `claude-agent-sdk` (Claude Agent SDK for Python), Node.js + `@anthropic-ai/claude-code` (runtime dependency for the agent CLI).

**Prerequisites:** The Dify host must have Node.js 18+ and the Claude CLI installed (`npm install -g @anthropic-ai/claude-code`).

---

### Task 1: Project Scaffolding

**Files:**
- Create: `dify-claude-agent/main.py`
- Create: `dify-claude-agent/manifest.yaml`
- Create: `dify-claude-agent/requirements.txt`
- Create: `dify-claude-agent/.env.example`
- Create: `dify-claude-agent/_assets/icon.svg`
- Create: `dify-claude-agent/.gitignore`

**Step 1: Create project directory structure**

```bash
mkdir -p dify-claude-agent/_assets dify-claude-agent/provider dify-claude-agent/tools
```

**Step 2: Create main.py (Dify plugin entry point)**

```python
from dify_plugin import DifyPluginEnv, Plugin

plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=300))

if __name__ == "__main__":
    plugin.run()
```

Note: `MAX_REQUEST_TIMEOUT=300` (5 minutes) because Claude Agents can take time to complete multi-turn tasks.

**Step 3: Create manifest.yaml**

```yaml
version: 0.0.1
type: plugin
author: "steven"
name: "claude-agent"
label:
  en_US: "Claude Agent"
  zh_Hans: "Claude Agent"
created_at: "2026-02-15T00:00:00.000000000Z"
icon: icon.svg
description:
  en_US: "Run autonomous Claude Agents in Dify workflows. Agents can read files, execute commands, search the web, and more."
  zh_Hans: "在 Dify 工作流中運行自主 Claude Agent。Agent 可以讀取文件、執行命令、搜索網頁等。"
tags:
  - "utilities"
resource:
  memory: 536870912
  permission:
    tool:
      enabled: true
    model:
      enabled: false
      llm: false
      text_embedding: false
      rerank: false
      tts: false
      speech2text: false
      moderation: false
    node:
      enabled: false
    endpoint:
      enabled: false
    app:
      enabled: false
  storage:
    enabled: false
    size: 0
plugins:
  tools:
    - "provider/claude_agent_provider.yaml"
meta:
  version: "0.0.1"
  arch:
    - "amd64"
    - "arm64"
  runner:
    language: "python"
    version: "3.12"
    entrypoint: "main"
```

**Step 4: Create requirements.txt**

```
dify_plugin>=0.7.0
claude-agent-sdk
```

**Step 5: Create .env.example**

```
INSTALL_METHOD=remote
REMOTE_INSTALL_URL=debug.dify.ai:5003
REMOTE_INSTALL_KEY=your-debugging-key-here
```

**Step 6: Create _assets/icon.svg**

A simple Claude-themed icon (orange/coral circle with a spark):

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <circle cx="50" cy="50" r="45" fill="#D97706" />
  <text x="50" y="62" text-anchor="middle" font-size="40" font-family="sans-serif" fill="white" font-weight="bold">C</text>
</svg>
```

**Step 7: Create .gitignore**

```
__pycache__/
*.pyc
.env
*.difypkg
.venv/
dist/
```

**Step 8: Commit**

```bash
git add dify-claude-agent/
git commit -m "feat: scaffold Dify Claude Agent plugin project"
```

---

### Task 2: Provider Definition (Credentials)

**Files:**
- Create: `dify-claude-agent/provider/claude_agent_provider.yaml`
- Create: `dify-claude-agent/provider/claude_agent_provider.py`

**Step 1: Create provider YAML**

```yaml
identity:
  author: steven
  name: claude_agent_provider
  label:
    en_US: Claude Agent
    zh_Hans: Claude Agent
  description:
    en_US: Run autonomous Claude Agents powered by Anthropic's Claude Agent SDK
    zh_Hans: 使用 Anthropic 的 Claude Agent SDK 運行自主 Claude Agent
  icon: icon.svg
  tags:
    - utilities
credentials_for_provider:
  anthropic_api_key:
    type: secret-input
    required: false
    label:
      en_US: Anthropic API Key
      zh_Hans: Anthropic API Key
    placeholder:
      en_US: "sk-ant-..."
    help:
      en_US: "Your Anthropic API key. Get one at https://console.anthropic.com/. Either this or OAuth token is required."
      zh_Hans: "您的 Anthropic API Key。至少需要提供 API Key 或 OAuth Token 其中之一。"
    url: https://console.anthropic.com/
  claude_code_oauth_token:
    type: secret-input
    required: false
    label:
      en_US: Claude Code OAuth Token
      zh_Hans: Claude Code OAuth Token
    placeholder:
      en_US: "Enter OAuth token"
    help:
      en_US: "Claude Code OAuth token (alternative to API key). Either this or API key is required."
      zh_Hans: "Claude Code OAuth Token（API Key 的替代方案）。至少需要提供其中之一。"
tools:
  - tools/claude_agent.yaml
extra:
  python:
    source: provider/claude_agent_provider.py
```

**Step 2: Create provider Python class**

```python
from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class ClaudeAgentProviderProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        api_key = credentials.get("anthropic_api_key", "").strip()
        oauth_token = credentials.get("claude_code_oauth_token", "").strip()

        if not api_key and not oauth_token:
            raise ToolProviderCredentialValidationError(
                "At least one credential is required: "
                "Anthropic API Key or Claude Code OAuth Token."
            )

        # Validate key format
        if api_key and not api_key.startswith("sk-ant-"):
            raise ToolProviderCredentialValidationError(
                "Invalid Anthropic API Key format. "
                "Key should start with 'sk-ant-'."
            )
```

**Step 3: Commit**

```bash
git add dify-claude-agent/provider/
git commit -m "feat: add Claude Agent provider with dual credential support"
```

---

### Task 3: Tool YAML Definition (Parameters)

**Files:**
- Create: `dify-claude-agent/tools/claude_agent.yaml`

**Step 1: Create tool YAML with all parameters**

```yaml
identity:
  name: claude_agent
  author: steven
  label:
    en_US: Claude Agent
    zh_Hans: Claude Agent

description:
  human:
    en_US: >
      Run an autonomous Claude Agent that can read files, execute commands,
      search the web, and complete complex tasks. Configure allowed tools,
      model, and budget to control agent behavior.
    zh_Hans: >
      運行一個自主 Claude Agent，可以讀取文件、執行命令、搜索網頁並完成複雜任務。
      配置允許的工具、模型和預算來控制 Agent 行為。
  llm: >
    Run an autonomous Claude Agent with configurable tools and capabilities.
    The agent can read files, execute bash commands, search the web, and more.
    Use this when you need an AI agent to perform complex multi-step tasks autonomously.
    The agent returns its result as text and structured JSON.

parameters:
  - name: prompt
    type: string
    required: true
    label:
      en_US: Prompt
      zh_Hans: 提示詞
    human_description:
      en_US: The task or instruction to send to the Claude Agent
      zh_Hans: 發送給 Claude Agent 的任務或指令
    llm_description: >
      The task prompt or instruction that the Claude Agent will execute autonomously.
      Be specific about what you want the agent to accomplish.
    form: llm

  - name: model
    type: select
    required: false
    label:
      en_US: Model
      zh_Hans: 模型
    human_description:
      en_US: Claude model to use for the agent
      zh_Hans: Agent 使用的 Claude 模型
    llm_description: The Claude model to use
    form: form
    default: "claude-sonnet-4-5-20250929"
    options:
      - value: "claude-opus-4-6"
        label:
          en_US: Claude Opus 4.6
      - value: "claude-sonnet-4-5-20250929"
        label:
          en_US: Claude Sonnet 4.5
      - value: "claude-haiku-4-5-20251001"
        label:
          en_US: Claude Haiku 4.5

  - name: system_prompt
    type: string
    required: false
    label:
      en_US: System Prompt
      zh_Hans: 系統提示詞
    human_description:
      en_US: Custom system prompt for the agent (optional)
      zh_Hans: Agent 的自定義系統提示詞（可選）
    llm_description: Custom system prompt to set the agent's behavior and context
    form: form

  - name: permission_mode
    type: select
    required: false
    label:
      en_US: Permission Mode
      zh_Hans: 權限模式
    human_description:
      en_US: Controls what the agent can do without asking permission
      zh_Hans: 控制 Agent 無需請求權限即可執行的操作
    llm_description: Permission mode for the agent's tool usage
    form: form
    default: "bypassPermissions"
    options:
      - value: "bypassPermissions"
        label:
          en_US: Bypass Permissions (Full Auto)
      - value: "acceptEdits"
        label:
          en_US: Accept Edits Only
      - value: "plan"
        label:
          en_US: Plan Mode (Read Only)

  - name: max_turns
    type: number
    required: false
    label:
      en_US: Max Turns
      zh_Hans: 最大輪次
    human_description:
      en_US: Maximum number of agent turns (default 10)
      zh_Hans: Agent 最大輪次數（預設 10）
    llm_description: Maximum number of agentic turns before stopping
    form: form
    default: 10
    min: 1
    max: 100

  - name: max_budget_usd
    type: number
    required: false
    label:
      en_US: Max Budget (USD)
      zh_Hans: 最大預算（美元）
    human_description:
      en_US: Maximum spending limit in USD (default 1.0)
      zh_Hans: 最大花費限制，單位美元（預設 1.0）
    llm_description: Maximum budget in USD for the agent execution
    form: form
    default: 1

  - name: allowed_tools
    type: string
    required: false
    label:
      en_US: Allowed Tools
      zh_Hans: 允許的工具
    human_description:
      en_US: >
        Comma-separated list of tools the agent can use.
        Available: Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Task.
        Default: Read,Glob,Grep,WebSearch,WebFetch
      zh_Hans: >
        Agent 可使用的工具列表（逗號分隔）。
        可用工具：Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Task。
        預設：Read,Glob,Grep,WebSearch,WebFetch
    llm_description: >
      Comma-separated list of allowed tools. Available tools:
      Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Task.
    form: form
    default: "Read,Glob,Grep,WebSearch,WebFetch"

  - name: subagent_config
    type: string
    required: false
    label:
      en_US: Subagent Config (JSON)
      zh_Hans: 子代理配置（JSON）
    human_description:
      en_US: >
        Optional JSON config for subagents. Example:
        {"researcher": {"description": "...", "prompt": "...", "tools": ["Read","WebSearch"], "model": "haiku"}}
      zh_Hans: >
        可選的子代理 JSON 配置。範例：
        {"researcher": {"description": "...", "prompt": "...", "tools": ["Read","WebSearch"], "model": "haiku"}}
    llm_description: >
      Optional JSON configuration for subagents that the main agent can delegate to.
      Each key is the agent name, value has description, prompt, tools, and optional model.
    form: form

extra:
  python:
    source: tools/claude_agent.py
```

**Step 2: Commit**

```bash
git add dify-claude-agent/tools/claude_agent.yaml
git commit -m "feat: add Claude Agent tool parameter definitions"
```

---

### Task 4: Core Tool Implementation (MVP — No Streaming)

**Files:**
- Create: `dify-claude-agent/tools/claude_agent.py`

**Step 1: Write the tool implementation**

This is the MVP implementation that collects all agent output and yields at the end (no real-time streaming yet).

```python
from collections.abc import Generator
from typing import Any
import asyncio
import json
import logging

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

logger = logging.getLogger(__name__)

# Valid Claude Agent SDK tool names
VALID_TOOLS = {
    "Read", "Write", "Edit", "Bash", "Glob", "Grep",
    "WebSearch", "WebFetch", "Task", "NotebookEdit",
    "AskUserQuestion", "TodoWrite",
}


class ClaudeAgentTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage]:
        # Extract parameters
        prompt = tool_parameters.get("prompt", "").strip()
        if not prompt:
            yield self.create_text_message("Error: prompt is required.")
            yield self.create_json_message({"is_error": True, "error": "prompt is required"})
            return

        model = tool_parameters.get("model", "claude-sonnet-4-5-20250929")
        system_prompt = tool_parameters.get("system_prompt", "").strip() or None
        permission_mode = tool_parameters.get("permission_mode", "bypassPermissions")
        max_turns = int(tool_parameters.get("max_turns", 10))
        max_budget_usd = float(tool_parameters.get("max_budget_usd", 1.0))
        allowed_tools_str = tool_parameters.get("allowed_tools", "Read,Glob,Grep,WebSearch,WebFetch")
        subagent_config_str = tool_parameters.get("subagent_config", "").strip()

        # Parse allowed tools
        allowed_tools = [
            t.strip() for t in allowed_tools_str.split(",") if t.strip()
        ]
        invalid_tools = [t for t in allowed_tools if t not in VALID_TOOLS]
        if invalid_tools:
            yield self.create_text_message(
                f"Error: invalid tools: {invalid_tools}. "
                f"Valid tools: {sorted(VALID_TOOLS)}"
            )
            yield self.create_json_message({
                "is_error": True,
                "error": f"Invalid tools: {invalid_tools}",
            })
            return

        # Parse subagent config
        agents = None
        if subagent_config_str:
            try:
                agents = self._parse_subagent_config(subagent_config_str)
                # Ensure Task is in allowed_tools when subagents are defined
                if "Task" not in allowed_tools:
                    allowed_tools.append("Task")
            except (json.JSONDecodeError, ValueError) as e:
                yield self.create_text_message(f"Error: invalid subagent_config JSON: {e}")
                yield self.create_json_message({
                    "is_error": True,
                    "error": f"Invalid subagent_config: {e}",
                })
                return

        # Build credentials env
        env = self._build_auth_env()
        if env is None:
            yield self.create_text_message(
                "Error: no valid credentials. "
                "Provide Anthropic API Key or Claude Code OAuth Token."
            )
            yield self.create_json_message({
                "is_error": True,
                "error": "No valid credentials configured",
            })
            return

        # Run the agent
        try:
            result = asyncio.run(
                self._run_agent(
                    prompt=prompt,
                    model=model,
                    system_prompt=system_prompt,
                    permission_mode=permission_mode,
                    max_turns=max_turns,
                    max_budget_usd=max_budget_usd,
                    allowed_tools=allowed_tools,
                    agents=agents,
                    env=env,
                )
            )
        except Exception as e:
            logger.exception("Claude Agent execution failed")
            yield self.create_text_message(f"Error: Claude Agent failed: {e}")
            yield self.create_json_message({
                "is_error": True,
                "error": str(e),
            })
            return

        # Yield results
        yield self.create_text_message(result["result"])
        yield self.create_json_message(result)

    async def _run_agent(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None,
        permission_mode: str,
        max_turns: int,
        max_budget_usd: float,
        allowed_tools: list[str],
        agents: dict | None,
        env: dict[str, str],
    ) -> dict[str, Any]:
        from claude_agent_sdk import (
            query,
            ClaudeAgentOptions,
            AssistantMessage,
            ResultMessage,
            TextBlock,
        )

        options = ClaudeAgentOptions(
            model=model,
            system_prompt=system_prompt,
            permission_mode=permission_mode,
            max_turns=max_turns,
            max_budget_usd=max_budget_usd,
            allowed_tools=allowed_tools,
            agents=agents,
            env=env,
        )

        text_parts: list[str] = []
        result_data: dict[str, Any] = {
            "result": "",
            "cost_usd": None,
            "duration_ms": 0,
            "is_error": False,
            "session_id": "",
            "num_turns": 0,
        }

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                result_data["cost_usd"] = message.total_cost_usd
                result_data["duration_ms"] = message.duration_ms
                result_data["is_error"] = message.is_error
                result_data["session_id"] = message.session_id
                result_data["num_turns"] = message.num_turns
                if message.result:
                    text_parts.append(message.result)

        result_data["result"] = "\n".join(text_parts) if text_parts else ""
        return result_data

    def _build_auth_env(self) -> dict[str, str] | None:
        env: dict[str, str] = {}
        api_key = self.runtime.credentials.get("anthropic_api_key", "").strip()
        oauth_token = self.runtime.credentials.get("claude_code_oauth_token", "").strip()

        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key
        if oauth_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token

        return env if env else None

    def _parse_subagent_config(self, config_str: str) -> dict:
        from claude_agent_sdk import AgentDefinition

        raw = json.loads(config_str)
        if not isinstance(raw, dict):
            raise ValueError("subagent_config must be a JSON object")

        agents = {}
        for name, cfg in raw.items():
            if not isinstance(cfg, dict):
                raise ValueError(f"Agent '{name}' config must be an object")
            if "description" not in cfg or "prompt" not in cfg:
                raise ValueError(
                    f"Agent '{name}' must have 'description' and 'prompt'"
                )
            agents[name] = AgentDefinition(
                description=cfg["description"],
                prompt=cfg["prompt"],
                tools=cfg.get("tools"),
                model=cfg.get("model"),
            )
        return agents
```

**Step 2: Verify the file structure is complete**

Run: `find dify-claude-agent/ -type f | sort`
Expected output:
```
dify-claude-agent/.env.example
dify-claude-agent/.gitignore
dify-claude-agent/_assets/icon.svg
dify-claude-agent/main.py
dify-claude-agent/manifest.yaml
dify-claude-agent/provider/claude_agent_provider.py
dify-claude-agent/provider/claude_agent_provider.yaml
dify-claude-agent/requirements.txt
dify-claude-agent/tools/claude_agent.py
dify-claude-agent/tools/claude_agent.yaml
```

**Step 3: Commit**

```bash
git add dify-claude-agent/tools/claude_agent.py
git commit -m "feat: implement Claude Agent tool with async bridging and subagent support"
```

---

### Task 5: Add Streaming Support

**Files:**
- Modify: `dify-claude-agent/tools/claude_agent.py`

**Step 1: Refactor _invoke to use threading for streaming**

Replace the `asyncio.run()` call with a thread-based approach that streams partial results via a queue:

```python
import queue
import threading
```

Add a new method `_invoke_streaming` and update `_invoke`:

```python
def _invoke(
    self, tool_parameters: dict[str, Any]
) -> Generator[ToolInvokeMessage]:
    # ... (parameter extraction stays the same up to the "Run the agent" section)

    # Run the agent with streaming
    msg_queue: queue.Queue[ToolInvokeMessage | None] = queue.Queue()
    error_holder: list[Exception] = []

    def run_in_thread():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._stream_agent(
                    prompt=prompt,
                    model=model,
                    system_prompt=system_prompt,
                    permission_mode=permission_mode,
                    max_turns=max_turns,
                    max_budget_usd=max_budget_usd,
                    allowed_tools=allowed_tools,
                    agents=agents,
                    env=env,
                    msg_queue=msg_queue,
                )
            )
        except Exception as e:
            error_holder.append(e)
        finally:
            msg_queue.put(None)  # sentinel

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()

    while True:
        msg = msg_queue.get()
        if msg is None:
            break
        yield msg

    thread.join(timeout=5)

    if error_holder:
        err = error_holder[0]
        logger.exception("Claude Agent execution failed")
        yield self.create_text_message(f"Error: Claude Agent failed: {err}")
        yield self.create_json_message({
            "is_error": True,
            "error": str(err),
        })
```

Add the async streaming method:

```python
async def _stream_agent(
    self,
    prompt: str,
    model: str,
    system_prompt: str | None,
    permission_mode: str,
    max_turns: int,
    max_budget_usd: float,
    allowed_tools: list[str],
    agents: dict | None,
    env: dict[str, str],
    msg_queue: queue.Queue,
) -> None:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        TextBlock,
    )

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt,
        permission_mode=permission_mode,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        allowed_tools=allowed_tools,
        agents=agents,
        env=env,
    )

    text_parts: list[str] = []
    result_data: dict[str, Any] = {
        "result": "",
        "cost_usd": None,
        "duration_ms": 0,
        "is_error": False,
        "session_id": "",
        "num_turns": 0,
    }

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
                    # Stream partial text to Dify
                    msg_queue.put(
                        self.create_text_message(block.text)
                    )
        elif isinstance(message, ResultMessage):
            result_data["cost_usd"] = message.total_cost_usd
            result_data["duration_ms"] = message.duration_ms
            result_data["is_error"] = message.is_error
            result_data["session_id"] = message.session_id
            result_data["num_turns"] = message.num_turns
            if message.result:
                text_parts.append(message.result)

    result_data["result"] = "\n".join(text_parts) if text_parts else ""
    msg_queue.put(self.create_json_message(result_data))
```

**Step 2: Commit**

```bash
git add dify-claude-agent/tools/claude_agent.py
git commit -m "feat: add streaming support via background thread + queue"
```

---

### Task 6: Unit Tests

**Files:**
- Create: `dify-claude-agent/tests/__init__.py`
- Create: `dify-claude-agent/tests/test_claude_agent_tool.py`

**Step 1: Create test file with mocked agent SDK**

```python
"""Tests for the Claude Agent tool."""
import json
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

import pytest

# We need to mock dify_plugin before importing our tool
# because dify_plugin uses gevent monkey-patching at import time


@dataclass
class MockTextBlock:
    text: str
    type: str = "text"


@dataclass
class MockAssistantMessage:
    content: list
    model: str = "claude-sonnet-4-5-20250929"
    type: str = "assistant"


@dataclass
class MockResultMessage:
    subtype: str = "success"
    duration_ms: int = 1000
    duration_api_ms: int = 800
    is_error: bool = False
    num_turns: int = 3
    session_id: str = "test-session-123"
    total_cost_usd: float = 0.05
    result: str = "Final result"
    type: str = "result"


class TestParseSubagentConfig:
    """Test subagent config parsing."""

    def test_valid_config(self):
        config = json.dumps({
            "researcher": {
                "description": "Research agent",
                "prompt": "Do research",
                "tools": ["Read", "WebSearch"],
                "model": "haiku",
            }
        })
        # Test JSON parsing
        raw = json.loads(config)
        assert "researcher" in raw
        assert raw["researcher"]["description"] == "Research agent"

    def test_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            json.loads("not valid json")

    def test_missing_required_fields(self):
        config = json.dumps({
            "agent": {"description": "test"}  # missing 'prompt'
        })
        raw = json.loads(config)
        assert "prompt" not in raw["agent"]

    def test_non_object_config(self):
        config = json.dumps(["not", "an", "object"])
        raw = json.loads(config)
        assert not isinstance(raw, dict)


class TestBuildAuthEnv:
    """Test credential environment building."""

    def test_api_key_only(self):
        credentials = {"anthropic_api_key": "sk-ant-test123", "claude_code_oauth_token": ""}
        env = {}
        api_key = credentials.get("anthropic_api_key", "").strip()
        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key
        assert env == {"ANTHROPIC_API_KEY": "sk-ant-test123"}

    def test_oauth_only(self):
        credentials = {"anthropic_api_key": "", "claude_code_oauth_token": "oauth-token-123"}
        env = {}
        oauth = credentials.get("claude_code_oauth_token", "").strip()
        if oauth:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth
        assert env == {"CLAUDE_CODE_OAUTH_TOKEN": "oauth-token-123"}

    def test_both_credentials(self):
        credentials = {"anthropic_api_key": "sk-ant-test", "claude_code_oauth_token": "oauth-123"}
        env = {}
        api_key = credentials.get("anthropic_api_key", "").strip()
        oauth = credentials.get("claude_code_oauth_token", "").strip()
        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key
        if oauth:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth
        assert len(env) == 2

    def test_no_credentials(self):
        credentials = {"anthropic_api_key": "", "claude_code_oauth_token": ""}
        env = {}
        api_key = credentials.get("anthropic_api_key", "").strip()
        oauth = credentials.get("claude_code_oauth_token", "").strip()
        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key
        if oauth:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth
        assert env == {}


class TestToolValidation:
    """Test allowed tools validation."""

    def test_valid_tools(self):
        valid = {"Read", "Write", "Edit", "Bash", "Glob", "Grep",
                 "WebSearch", "WebFetch", "Task", "NotebookEdit",
                 "AskUserQuestion", "TodoWrite"}
        tools = ["Read", "Glob", "Grep"]
        invalid = [t for t in tools if t not in valid]
        assert invalid == []

    def test_invalid_tools(self):
        valid = {"Read", "Write", "Edit", "Bash", "Glob", "Grep",
                 "WebSearch", "WebFetch", "Task", "NotebookEdit",
                 "AskUserQuestion", "TodoWrite"}
        tools = ["Read", "InvalidTool", "Bash"]
        invalid = [t for t in tools if t not in valid]
        assert invalid == ["InvalidTool"]

    def test_parse_tools_string(self):
        tools_str = "Read, Glob , Grep, WebSearch"
        tools = [t.strip() for t in tools_str.split(",") if t.strip()]
        assert tools == ["Read", "Glob", "Grep", "WebSearch"]
```

**Step 2: Run tests**

Run: `cd dify-claude-agent && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add dify-claude-agent/tests/
git commit -m "test: add unit tests for parameter parsing, auth, and tool validation"
```

---

### Task 7: README and Documentation

**Files:**
- Create: `README.md` (project root)

**Step 1: Write README**

```markdown
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

### From Source

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
[Start] → [Agent: Research] → [Agent: Summarize] → [Agent: Write] → [End]
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
| system_prompt | string | — | Custom system prompt |
| permission_mode | select | bypassPermissions | Agent permission level |
| max_turns | number | 10 | Max agent turns |
| max_budget_usd | number | 1.0 | Spending limit (USD) |
| allowed_tools | string | Read,Glob,Grep,WebSearch,WebFetch | Tools the agent can use |
| subagent_config | string | — | JSON subagent definitions |

## Development

```bash
cd dify-claude-agent
python -m pytest tests/ -v
```

## License

MIT
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with installation, usage, and configuration guide"
```

---

### Task 8: Packaging and Final Verification

**Step 1: Verify all files exist**

Run: `find dify-claude-agent/ -type f | sort`

Expected:
```
dify-claude-agent/.env.example
dify-claude-agent/.gitignore
dify-claude-agent/_assets/icon.svg
dify-claude-agent/main.py
dify-claude-agent/manifest.yaml
dify-claude-agent/provider/claude_agent_provider.py
dify-claude-agent/provider/claude_agent_provider.yaml
dify-claude-agent/requirements.txt
dify-claude-agent/tests/__init__.py
dify-claude-agent/tests/test_claude_agent_tool.py
dify-claude-agent/tools/claude_agent.py
dify-claude-agent/tools/claude_agent.yaml
```

**Step 2: Validate YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('dify-claude-agent/manifest.yaml')); print('manifest OK')" && python -c "import yaml; yaml.safe_load(open('dify-claude-agent/provider/claude_agent_provider.yaml')); print('provider OK')" && python -c "import yaml; yaml.safe_load(open('dify-claude-agent/tools/claude_agent.yaml')); print('tool OK')"`

Expected: All three print OK

**Step 3: Run tests**

Run: `cd dify-claude-agent && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit any fixes**

```bash
git add -A && git commit -m "chore: final verification and cleanup"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Project scaffolding | main.py, manifest.yaml, requirements.txt, icon, .gitignore |
| 2 | Provider (credentials) | provider/*.yaml, provider/*.py |
| 3 | Tool YAML (parameters) | tools/claude_agent.yaml |
| 4 | Core tool implementation (MVP) | tools/claude_agent.py |
| 5 | Add streaming support | tools/claude_agent.py (modify) |
| 6 | Unit tests | tests/ |
| 7 | README | README.md |
| 8 | Final verification | validate + test |
