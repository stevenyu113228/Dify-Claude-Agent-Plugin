from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class ClaudeAgentProviderProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        api_key = credentials.get("anthropic_api_key", "").strip()
        oauth_token = credentials.get("claude_code_oauth_token", "").strip()
        base_url = credentials.get("anthropic_base_url", "").strip()
        auth_token = credentials.get("anthropic_auth_token", "").strip()

        # Custom endpoint fields must be provided as a pair
        custom_any = bool(base_url) or bool(auth_token)
        custom_all = bool(base_url) and bool(auth_token)

        if custom_any and not custom_all:
            missing = "Custom Endpoint Auth Token" if not auth_token else "Custom API Base URL"
            raise ToolProviderCredentialValidationError(
                "Custom endpoint requires both Base URL and Auth Token. "
                f"Missing: {missing}."
            )

        if base_url and not (
            base_url.startswith("http://") or base_url.startswith("https://")
        ):
            raise ToolProviderCredentialValidationError(
                "Custom API Base URL must start with 'http://' or 'https://'."
            )

        has_mode = bool(api_key) or bool(oauth_token) or custom_all
        if not has_mode:
            raise ToolProviderCredentialValidationError(
                "At least one credential is required: "
                "Anthropic API Key, Claude Code OAuth Token, "
                "or Custom Endpoint (Base URL + Auth Token)."
            )

        if api_key and not api_key.startswith("sk-ant-"):
            raise ToolProviderCredentialValidationError(
                "Invalid Anthropic API Key format. "
                "Key should start with 'sk-ant-'."
            )
