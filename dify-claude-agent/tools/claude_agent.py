from collections.abc import Generator
from typing import Any
import asyncio
import json
import logging
import queue
import threading

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
        allowed_tools_str = tool_parameters.get(
            "allowed_tools", "Read,Glob,Grep,WebSearch,WebFetch"
        )
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
                yield self.create_text_message(
                    f"Error: invalid subagent_config JSON: {e}"
                )
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

        # Run the agent with streaming via background thread
        msg_queue: queue.Queue[ToolInvokeMessage | None] = queue.Queue()
        error_holder: list[Exception] = []

        def run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
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
                loop.close()
                msg_queue.put(None)  # sentinel

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

        while True:
            try:
                msg = msg_queue.get(timeout=5.0)
            except queue.Empty:
                if not thread.is_alive():
                    break
                continue
            if msg is None:
                break
            yield msg

        thread.join(timeout=5)

        if error_holder:
            err = error_holder[0]
            logger.error("Claude Agent execution failed", exc_info=err)
            yield self.create_text_message(f"Error: Claude Agent failed: {err}")
            yield self.create_json_message({
                "is_error": True,
                "error": str(err),
            })

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
        msg_queue: "queue.Queue[ToolInvokeMessage | None]",
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
                        # Stream partial text to Dify UI
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
                    result_data["result"] = message.result

        # Use ResultMessage.result if available, otherwise fall back to
        # collected text parts (avoids duplicate content)
        if not result_data["result"]:
            result_data["result"] = "\n".join(text_parts) if text_parts else ""
        msg_queue.put(self.create_json_message(result_data))

    def _build_auth_env(self) -> dict[str, str] | None:
        env: dict[str, str] = {}
        api_key = self.runtime.credentials.get("anthropic_api_key", "").strip()
        oauth_token = self.runtime.credentials.get(
            "claude_code_oauth_token", ""
        ).strip()

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
