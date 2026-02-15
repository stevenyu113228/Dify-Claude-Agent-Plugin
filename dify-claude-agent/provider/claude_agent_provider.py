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

        if api_key and not api_key.startswith("sk-ant-"):
            raise ToolProviderCredentialValidationError(
                "Invalid Anthropic API Key format. "
                "Key should start with 'sk-ant-'."
            )
