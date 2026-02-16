"""
Unit tests for ClaudeAgentTool parameter parsing, auth, and tool validation.

Since dify_plugin and claude_agent_sdk are not installed in the test environment,
we test the pure logic extracted from the implementation. Where we need to test
class methods (like _build_auth_env), we mock the unavailable imports and
construct lightweight stand-ins.
"""

import json
import sys
import types
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: mock dify_plugin + claude_agent_sdk so the module can be imported
# ---------------------------------------------------------------------------

_dify_plugin_mod = types.ModuleType("dify_plugin")
_dify_plugin_mod.Tool = type("Tool", (), {})  # placeholder base class
_dify_plugin_mod.ToolProvider = type("ToolProvider", (), {})  # placeholder base class
_dify_entities_mod = types.ModuleType("dify_plugin.entities")
_dify_entities_tool_mod = types.ModuleType("dify_plugin.entities.tool")
_dify_entities_tool_mod.ToolInvokeMessage = type("ToolInvokeMessage", (), {})
_dify_errors_mod = types.ModuleType("dify_plugin.errors")
_dify_errors_tool_mod = types.ModuleType("dify_plugin.errors.tool")


class _FakeToolProviderCredentialValidationError(Exception):
    pass


_dify_errors_tool_mod.ToolProviderCredentialValidationError = (
    _FakeToolProviderCredentialValidationError
)

sys.modules["dify_plugin"] = _dify_plugin_mod
sys.modules["dify_plugin.entities"] = _dify_entities_mod
sys.modules["dify_plugin.entities.tool"] = _dify_entities_tool_mod
sys.modules["dify_plugin.errors"] = _dify_errors_mod
sys.modules["dify_plugin.errors.tool"] = _dify_errors_tool_mod

_claude_sdk_mod = types.ModuleType("claude_agent_sdk")
_claude_sdk_mod.query = MagicMock()
_claude_sdk_mod.ClaudeAgentOptions = MagicMock()
_claude_sdk_mod.AssistantMessage = MagicMock()
_claude_sdk_mod.ResultMessage = MagicMock()
_claude_sdk_mod.TextBlock = MagicMock()


class _FakeAgentDefinition:
    """Minimal stand-in for AgentDefinition used by _parse_subagent_config."""
    def __init__(self, *, description, prompt, tools=None, model=None):
        self.description = description
        self.prompt = prompt
        self.tools = tools
        self.model = model


_claude_sdk_mod.AgentDefinition = _FakeAgentDefinition
sys.modules["claude_agent_sdk"] = _claude_sdk_mod

# Now we can safely import the modules under test
from tools.claude_agent import VALID_TOOLS, ClaudeAgentTool  # noqa: E402
from provider.claude_agent_provider import ClaudeAgentProviderProvider  # noqa: E402


# ===========================================================================
# 1. VALID_TOOLS set membership
# ===========================================================================

class TestValidTools:
    """Verify tool-name validation against the VALID_TOOLS set."""

    EXPECTED_VALID = [
        "Read", "Write", "Edit", "Bash", "Glob", "Grep",
        "WebSearch", "WebFetch", "Task", "NotebookEdit",
        "AskUserQuestion", "TodoWrite", "Skill",
    ]

    @pytest.mark.parametrize("tool_name", EXPECTED_VALID)
    def test_valid_tool_is_accepted(self, tool_name):
        assert tool_name in VALID_TOOLS

    @pytest.mark.parametrize("tool_name", [
        "read",          # wrong case
        "WRITE",         # all caps
        "BashExec",      # non-existent
        "web_search",    # snake_case variant
        "",              # empty string
        " Bash",         # leading space
    ])
    def test_invalid_tool_is_rejected(self, tool_name):
        assert tool_name not in VALID_TOOLS

    def test_expected_count(self):
        """Ensure the set contains exactly the expected number of tools."""
        assert len(VALID_TOOLS) == 13


# ===========================================================================
# 2. Allowed-tools comma-separated parsing
# ===========================================================================

class TestAllowedToolsParsing:
    """
    Reproduce the parsing logic from _invoke:
        allowed_tools = [t.strip() for t in allowed_tools_str.split(",") if t.strip()]
    """

    @staticmethod
    def _parse(raw: str) -> list[str]:
        return [t.strip() for t in raw.split(",") if t.strip()]

    def test_simple_csv(self):
        assert self._parse("Read,Write,Edit") == ["Read", "Write", "Edit"]

    def test_csv_with_spaces(self):
        assert self._parse("Read , Write , Edit") == ["Read", "Write", "Edit"]

    def test_trailing_comma(self):
        assert self._parse("Read,Write,") == ["Read", "Write"]

    def test_leading_comma(self):
        assert self._parse(",Read,Write") == ["Read", "Write"]

    def test_empty_string(self):
        assert self._parse("") == []

    def test_whitespace_only(self):
        assert self._parse("   ") == []

    def test_single_tool(self):
        assert self._parse("Bash") == ["Bash"]

    def test_multiple_commas_between(self):
        result = self._parse("Read,,,,Write")
        assert result == ["Read", "Write"]

    def test_default_value(self):
        """The default from tool_parameters.get is this string."""
        default = "Read,Glob,Grep,WebSearch,WebFetch"
        result = self._parse(default)
        assert result == ["Read", "Glob", "Grep", "WebSearch", "WebFetch"]
        # All defaults should be valid
        assert all(t in VALID_TOOLS for t in result)

    def test_invalid_tool_detection(self):
        """After parsing, invalid tools should be detectable."""
        parsed = self._parse("Read,FakeTool,Write")
        invalid = [t for t in parsed if t not in VALID_TOOLS]
        assert invalid == ["FakeTool"]


# ===========================================================================
# 2b. MCP tool name bypass in allowed_tools validation
# ===========================================================================

class TestMcpToolNameBypass:
    """Tools prefixed with mcp__ should bypass VALID_TOOLS validation."""

    @staticmethod
    def _validate(tools: list[str]) -> list[str]:
        """Reproduce the validation logic from _invoke."""
        return [t for t in tools if t not in VALID_TOOLS and not t.startswith("mcp__")]

    @pytest.mark.parametrize("tool_name", [
        "mcp__context7__resolve-library-id",
        "mcp__context7__query-docs",
        "mcp__custom__my_tool",
        "mcp__",
    ])
    def test_mcp_prefixed_tools_accepted(self, tool_name):
        assert self._validate([tool_name]) == []

    def test_mcp_mixed_with_valid_tools(self):
        tools = ["Read", "mcp__context7__query-docs", "Write"]
        assert self._validate(tools) == []

    def test_non_mcp_invalid_still_rejected(self):
        tools = ["Read", "mcp__context7__query-docs", "FakeTool"]
        assert self._validate(tools) == ["FakeTool"]

    def test_mcp_without_double_underscore_rejected(self):
        """'mcp_foo' (single underscore) is not a valid MCP prefix."""
        assert self._validate(["mcp_foo"]) == ["mcp_foo"]


# ===========================================================================
# 3. Auth env building (_build_auth_env)
# ===========================================================================

class TestBuildAuthEnv:
    """Test _build_auth_env by constructing a ClaudeAgentTool with mocked runtime."""

    @staticmethod
    def _make_tool(credentials: dict) -> ClaudeAgentTool:
        tool = ClaudeAgentTool.__new__(ClaudeAgentTool)
        tool.runtime = MagicMock()
        tool.runtime.credentials = credentials
        return tool

    def test_api_key_only(self):
        tool = self._make_tool({"anthropic_api_key": "sk-test-123"})
        env = tool._build_auth_env()
        assert env == {"ANTHROPIC_API_KEY": "sk-test-123"}

    def test_oauth_only(self):
        tool = self._make_tool({"claude_code_oauth_token": "oauth-tok-abc"})
        env = tool._build_auth_env()
        assert env == {"CLAUDE_CODE_OAUTH_TOKEN": "oauth-tok-abc"}

    def test_both_credentials(self):
        tool = self._make_tool({
            "anthropic_api_key": "sk-key",
            "claude_code_oauth_token": "oauth-tok",
        })
        env = tool._build_auth_env()
        assert env == {
            "ANTHROPIC_API_KEY": "sk-key",
            "CLAUDE_CODE_OAUTH_TOKEN": "oauth-tok",
        }

    def test_neither_returns_none(self):
        tool = self._make_tool({})
        env = tool._build_auth_env()
        assert env is None

    def test_empty_strings_returns_none(self):
        tool = self._make_tool({
            "anthropic_api_key": "",
            "claude_code_oauth_token": "  ",
        })
        env = tool._build_auth_env()
        assert env is None

    def test_whitespace_stripped(self):
        tool = self._make_tool({"anthropic_api_key": "  sk-padded  "})
        env = tool._build_auth_env()
        assert env == {"ANTHROPIC_API_KEY": "sk-padded"}

    def test_missing_keys_returns_none(self):
        """When the credential keys are entirely absent from the dict."""
        tool = self._make_tool({"some_other_key": "value"})
        env = tool._build_auth_env()
        assert env is None

    def test_custom_endpoint_all_fields(self):
        """Custom endpoint base_url + auth_token are added to env."""
        tool = self._make_tool({
            "anthropic_base_url": "https://router.requesty.ai/v1",
            "anthropic_auth_token": "req-token-xyz",
        })
        env = tool._build_auth_env()
        assert env == {
            "ANTHROPIC_BASE_URL": "https://router.requesty.ai/v1",
            "ANTHROPIC_AUTH_TOKEN": "req-token-xyz",
        }

    def test_custom_endpoint_with_api_key(self):
        """Custom endpoint fields coexist with API key."""
        tool = self._make_tool({
            "anthropic_api_key": "sk-ant-key",
            "anthropic_base_url": "https://proxy.example.com/v1",
            "anthropic_auth_token": "proxy-token",
        })
        env = tool._build_auth_env()
        assert env == {
            "ANTHROPIC_API_KEY": "sk-ant-key",
            "ANTHROPIC_BASE_URL": "https://proxy.example.com/v1",
            "ANTHROPIC_AUTH_TOKEN": "proxy-token",
        }

    def test_custom_endpoint_whitespace_stripped(self):
        """Whitespace is stripped from custom endpoint fields."""
        tool = self._make_tool({
            "anthropic_base_url": "  https://proxy.example.com  ",
            "anthropic_auth_token": "  tok-123  ",
        })
        env = tool._build_auth_env()
        assert env == {
            "ANTHROPIC_BASE_URL": "https://proxy.example.com",
            "ANTHROPIC_AUTH_TOKEN": "tok-123",
        }


# ===========================================================================
# 4. Subagent config parsing (_parse_subagent_config)
# ===========================================================================

class TestParseSubagentConfig:
    """Test _parse_subagent_config with mocked AgentDefinition."""

    @staticmethod
    def _make_tool() -> ClaudeAgentTool:
        tool = ClaudeAgentTool.__new__(ClaudeAgentTool)
        return tool

    def test_valid_single_agent(self):
        config = json.dumps({
            "researcher": {
                "description": "Research agent",
                "prompt": "You are a researcher.",
            }
        })
        tool = self._make_tool()
        agents = tool._parse_subagent_config(config)
        assert "researcher" in agents
        assert agents["researcher"].description == "Research agent"
        assert agents["researcher"].prompt == "You are a researcher."
        assert agents["researcher"].tools is None
        assert agents["researcher"].model is None

    def test_valid_multiple_agents(self):
        config = json.dumps({
            "coder": {
                "description": "Writes code",
                "prompt": "You write code.",
                "tools": ["Read", "Write", "Edit"],
                "model": "claude-sonnet-4-5",
            },
            "reviewer": {
                "description": "Reviews code",
                "prompt": "You review code.",
            },
        })
        tool = self._make_tool()
        agents = tool._parse_subagent_config(config)
        assert len(agents) == 2
        assert agents["coder"].tools == ["Read", "Write", "Edit"]
        assert agents["coder"].model == "claude-sonnet-4-5"
        assert agents["reviewer"].tools is None

    def test_invalid_json(self):
        tool = self._make_tool()
        with pytest.raises(json.JSONDecodeError):
            tool._parse_subagent_config("{not valid json}")

    def test_non_object_top_level(self):
        """Top-level must be a JSON object, not an array."""
        tool = self._make_tool()
        with pytest.raises(ValueError, match="must be a JSON object"):
            tool._parse_subagent_config('[{"description":"a","prompt":"b"}]')

    def test_non_object_agent_config(self):
        """Each agent value must be an object."""
        tool = self._make_tool()
        with pytest.raises(ValueError, match="config must be an object"):
            tool._parse_subagent_config('{"agent1": "not-an-object"}')

    def test_missing_description(self):
        config = json.dumps({
            "agent1": {"prompt": "Do stuff"},
        })
        tool = self._make_tool()
        with pytest.raises(ValueError, match="must have 'description' and 'prompt'"):
            tool._parse_subagent_config(config)

    def test_missing_prompt(self):
        config = json.dumps({
            "agent1": {"description": "An agent"},
        })
        tool = self._make_tool()
        with pytest.raises(ValueError, match="must have 'description' and 'prompt'"):
            tool._parse_subagent_config(config)

    def test_empty_object(self):
        """Empty object is valid but produces no agents."""
        tool = self._make_tool()
        agents = tool._parse_subagent_config("{}")
        assert agents == {}

    def test_scalar_top_level(self):
        """A scalar JSON value (string) should fail."""
        tool = self._make_tool()
        with pytest.raises(ValueError, match="must be a JSON object"):
            tool._parse_subagent_config('"just a string"')

    def test_number_top_level(self):
        tool = self._make_tool()
        with pytest.raises(ValueError, match="must be a JSON object"):
            tool._parse_subagent_config("42")

    def test_null_top_level(self):
        tool = self._make_tool()
        with pytest.raises(ValueError, match="must be a JSON object"):
            tool._parse_subagent_config("null")


# ===========================================================================
# 4b. MCP servers config parsing (_parse_mcp_servers)
# ===========================================================================

class TestParseMcpServers:
    """Test _parse_mcp_servers with various inputs."""

    @staticmethod
    def _make_tool() -> ClaudeAgentTool:
        tool = ClaudeAgentTool.__new__(ClaudeAgentTool)
        return tool

    def test_valid_single_server(self):
        config = json.dumps({
            "context7": {
                "type": "url",
                "url": "https://mcp.context7.com/mcp",
            }
        })
        tool = self._make_tool()
        result = tool._parse_mcp_servers(config)
        assert "context7" in result
        assert result["context7"]["type"] == "url"
        assert result["context7"]["url"] == "https://mcp.context7.com/mcp"

    def test_valid_multiple_servers(self):
        config = json.dumps({
            "context7": {
                "type": "url",
                "url": "https://mcp.context7.com/mcp",
            },
            "custom": {
                "type": "stdio",
                "command": "node",
                "args": ["server.js"],
            },
        })
        tool = self._make_tool()
        result = tool._parse_mcp_servers(config)
        assert len(result) == 2
        assert result["context7"]["type"] == "url"
        assert result["custom"]["command"] == "node"

    def test_invalid_json(self):
        tool = self._make_tool()
        with pytest.raises(json.JSONDecodeError):
            tool._parse_mcp_servers("{not valid json}")

    def test_non_object_top_level(self):
        tool = self._make_tool()
        with pytest.raises(ValueError, match="must be a JSON object"):
            tool._parse_mcp_servers('[{"type": "url"}]')

    def test_non_object_server_config(self):
        tool = self._make_tool()
        with pytest.raises(ValueError, match="config must be an object"):
            tool._parse_mcp_servers('{"server1": "not-an-object"}')

    def test_empty_object(self):
        tool = self._make_tool()
        result = tool._parse_mcp_servers("{}")
        assert result == {}


# ===========================================================================
# 5. Provider credential validation
# ===========================================================================

class TestProviderValidation:
    """Test ClaudeAgentProviderProvider._validate_credentials."""

    @staticmethod
    def _make_provider() -> ClaudeAgentProviderProvider:
        provider = ClaudeAgentProviderProvider.__new__(ClaudeAgentProviderProvider)
        return provider

    # --- Valid modes ---

    def test_valid_api_key(self):
        provider = self._make_provider()
        provider._validate_credentials({"anthropic_api_key": "sk-ant-test123"})

    def test_valid_oauth(self):
        provider = self._make_provider()
        provider._validate_credentials({"claude_code_oauth_token": "oauth-tok-abc"})

    def test_valid_custom_endpoint(self):
        provider = self._make_provider()
        provider._validate_credentials({
            "anthropic_base_url": "https://router.requesty.ai",
            "anthropic_auth_token": "req-token",
        })

    def test_valid_api_key_with_custom_endpoint(self):
        """API key and custom endpoint can coexist."""
        provider = self._make_provider()
        provider._validate_credentials({
            "anthropic_api_key": "sk-ant-test123",
            "anthropic_base_url": "https://proxy.example.com",
            "anthropic_auth_token": "proxy-token",
        })

    # --- Invalid modes ---

    def test_no_credentials(self):
        provider = self._make_provider()
        with pytest.raises(_FakeToolProviderCredentialValidationError, match="At least one credential"):
            provider._validate_credentials({})

    def test_bad_api_key_format(self):
        provider = self._make_provider()
        with pytest.raises(_FakeToolProviderCredentialValidationError, match="Invalid Anthropic API Key format"):
            provider._validate_credentials({"anthropic_api_key": "bad-key-123"})

    def test_base_url_without_auth_token(self):
        provider = self._make_provider()
        with pytest.raises(_FakeToolProviderCredentialValidationError, match="Missing.*Auth Token"):
            provider._validate_credentials({
                "anthropic_base_url": "https://proxy.example.com",
            })

    def test_auth_token_without_base_url(self):
        provider = self._make_provider()
        with pytest.raises(_FakeToolProviderCredentialValidationError, match="Missing.*Base URL"):
            provider._validate_credentials({
                "anthropic_auth_token": "tok-123",
            })

    def test_invalid_url_format(self):
        provider = self._make_provider()
        with pytest.raises(_FakeToolProviderCredentialValidationError, match="must start with"):
            provider._validate_credentials({
                "anthropic_base_url": "ftp://proxy.example.com",
                "anthropic_auth_token": "tok-123",
            })

    def test_empty_strings_treated_as_absent(self):
        """All-empty credentials should fail as no mode satisfied."""
        provider = self._make_provider()
        with pytest.raises(_FakeToolProviderCredentialValidationError, match="At least one credential"):
            provider._validate_credentials({
                "anthropic_api_key": "",
                "claude_code_oauth_token": "  ",
                "anthropic_base_url": "",
                "anthropic_auth_token": "",
            })

    def test_http_url_accepted(self):
        """http:// URLs are valid (for local development proxies)."""
        provider = self._make_provider()
        provider._validate_credentials({
            "anthropic_base_url": "http://localhost:8080",
            "anthropic_auth_token": "dev-token",
        })
