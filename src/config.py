"""Application configuration with no third-party dotenv dependency."""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path | None = None) -> None:
    """Load simple KEY=VALUE pairs without overriding existing environment values."""

    dotenv_path = path or PROJECT_ROOT / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _as_bool(value: str, default: bool) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the chatbot and MCP subprocesses."""

    gemini_api_key: str
    gemini_model: str
    gemini_base_url: str
    mcp_protocol_version: str
    request_timeout: float
    confirm_tools: bool
    log_path: Path
    server_config_path: Path

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv()
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip(),
            gemini_base_url=os.getenv(
                "GEMINI_API_URL", "https://generativelanguage.googleapis.com"
            ).strip(),
            mcp_protocol_version="2025-11-25",
            request_timeout=float(os.getenv("MCP_REQUEST_TIMEOUT", "30")),
            confirm_tools=_as_bool(os.getenv("MCP_CONFIRM_TOOLS", "true"), True),
            log_path=PROJECT_ROOT / "logs" / "mcp.jsonl",
            server_config_path=PROJECT_ROOT / "mcp_servers.json",
        )


@dataclass(frozen=True)
class ServerDefinition:
    """Validated configuration for one local or remote MCP server."""

    transport: str
    command: tuple[str, ...] = ()
    url: str = ""
    auth_token: str = ""
    environment: tuple[tuple[str, str], ...] = ()


def load_server_definitions(path: Path) -> dict[str, ServerDefinition]:
    """Read enabled server definitions and expand safe project placeholders."""

    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    definitions: dict[str, ServerDefinition] = {}
    replacements = {
        "{python}": sys.executable,
        "{workspace}": str(PROJECT_ROOT),
        "{workspace_posix}": PROJECT_ROOT.as_posix(),
        "{node}": shutil.which("node") or "node",
        "{filesystem_server}": str(
            PROJECT_ROOT
            / "node_modules"
            / "@modelcontextprotocol"
            / "server-filesystem"
            / "dist"
            / "index.js"
        ),
    }

    for name, definition in data.get("servers", {}).items():
        if not isinstance(definition, dict):
            raise ValueError(f"Server '{name}' must be a JSON object")
        if not definition.get("enabled", True):
            continue
        transport = str(definition.get("transport", "stdio"))
        if transport == "stdio":
            raw_command = definition.get("command")
            if not isinstance(raw_command, list) or not raw_command:
                raise ValueError(
                    f"Server '{name}' must define a non-empty command list"
                )
            command = tuple(
                replacements.get(str(part), str(part)) for part in raw_command
            )
            raw_environment = definition.get("environment", {})
            if not isinstance(raw_environment, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in raw_environment.items()
            ):
                raise ValueError(
                    f"Server '{name}' environment must contain string pairs"
                )
            environment = tuple(
                (key, replacements.get(value, value))
                for key, value in raw_environment.items()
            )
            definitions[name] = ServerDefinition(
                transport=transport,
                command=command,
                environment=environment,
            )
            continue
        if transport == "streamable_http":
            raw_url = definition.get("url", "")
            url_env = definition.get("url_env", "")
            if raw_url and not isinstance(raw_url, str):
                raise ValueError(f"Server '{name}' URL must be a string")
            if url_env and not isinstance(url_env, str):
                raise ValueError(f"Server '{name}' url_env must be a string")
            url = str(raw_url).strip()
            if not url and url_env:
                url = os.getenv(url_env, "").strip()
            if not url:
                raise ValueError(f"Server '{name}' does not have a remote URL")
            token_env = definition.get("auth_token_env", "")
            if token_env and not isinstance(token_env, str):
                raise ValueError(
                    f"Server '{name}' auth_token_env must be a string"
                )
            auth_token = os.getenv(token_env, "").strip() if token_env else ""
            definitions[name] = ServerDefinition(
                transport=transport,
                url=url,
                auth_token=auth_token,
            )
            continue
        raise ValueError(f"Server '{name}' has unsupported transport '{transport}'")
    return definitions
