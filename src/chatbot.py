"""Interactive Gemini host that bridges model function calls to MCP servers."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT, Settings, load_server_definitions
from src.mcp_client import JsonlExchangeLogger, MCPError, MCPStdioClient


JsonObject = dict[str, Any]


class GeminiAPIError(RuntimeError):
    """Raised for an unsuccessful Gemini generateContent request."""


class GeminiGenerateContentClient:
    """Small direct REST client for Gemini without a provider SDK."""

    def __init__(
        self, api_key: str, model: str, base_url: str, timeout: float = 60
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _build_payload(
        self, contents: list[JsonObject], tools: list[JsonObject]
    ) -> JsonObject:
        payload: JsonObject = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are a network operations assistant. Use available "
                            "tools when they are needed. Explain tool results clearly "
                            "and never claim an action was completed unless its tool "
                            "result confirms success. Reply in the language used by "
                            "the user."
                        )
                    }
                ]
            },
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 2048},
        }
        if tools:
            payload["tools"] = [{"functionDeclarations": tools}]
            payload["toolConfig"] = {
                "functionCallingConfig": {"mode": "AUTO"}
            }
        return payload

    def generate_content(
        self, contents: list[JsonObject], tools: list[JsonObject]
    ) -> JsonObject:
        model = urllib.parse.quote(self.model, safe="-._")
        url = f"{self.base_url}/v1beta/models/{model}:generateContent"
        request = urllib.request.Request(
            url,
            data=json.dumps(
                self._build_payload(contents, tools), ensure_ascii=False
            ).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GeminiAPIError(
                f"Gemini API returned HTTP {exc.code}: {body}"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise GeminiAPIError(f"Could not reach the Gemini API: {exc}") from exc
        candidates = result.get("candidates") if isinstance(result, dict) else None
        if not isinstance(candidates, list) or not candidates:
            feedback = result.get("promptFeedback", {}) if isinstance(result, dict) else {}
            raise GeminiAPIError(
                f"Gemini returned no response candidate. Prompt feedback: {feedback}"
            )
        content = candidates[0].get("content")
        if not isinstance(content, dict) or not isinstance(content.get("parts"), list):
            raise GeminiAPIError("Gemini API returned an unexpected response")
        return result


class MCPChatbot:
    """Own conversation context and route Gemini function calls to MCP clients."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = JsonlExchangeLogger(settings.log_path, display=True)
        self.gemini = GeminiGenerateContentClient(
            settings.gemini_api_key,
            settings.gemini_model,
            settings.gemini_base_url,
        )
        self.clients: dict[str, MCPStdioClient] = {}
        self.tool_routes: dict[str, tuple[MCPStdioClient, str]] = {}
        self.tools: list[JsonObject] = []
        self.messages: list[JsonObject] = []

    @staticmethod
    def _public_tool_name(server: str, tool: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", f"{server}__{tool}")
        return sanitized[:64]

    def start_servers(self) -> None:
        definitions = load_server_definitions(self.settings.server_config_path)
        for name, command in definitions.items():
            client = MCPStdioClient(
                name=name,
                command=command,
                logger=self.logger,
                protocol_version=self.settings.mcp_protocol_version,
                timeout=self.settings.request_timeout,
                cwd=PROJECT_ROOT,
            )
            try:
                client.connect()
                self.clients[name] = client
                server_tools = client.list_tools()
                for tool in server_tools:
                    native_name = tool.get("name")
                    schema = tool.get("inputSchema")
                    if not isinstance(native_name, str) or not isinstance(schema, dict):
                        continue
                    public_name = self._public_tool_name(name, native_name)
                    if public_name in self.tool_routes:
                        print(f"Warning: duplicate tool alias ignored: {public_name}")
                        continue
                    self.tool_routes[public_name] = (client, native_name)
                    self.tools.append(
                        {
                            "name": public_name,
                            "description": (
                                f"MCP server '{name}': "
                                f"{tool.get('description', native_name)}"
                            ),
                            "parametersJsonSchema": schema,
                        }
                    )
                print(f"Connected: {name} ({len(server_tools)} tools)")
            except Exception as exc:
                client.close()
                print(f"Warning: server '{name}' is unavailable: {exc}")

    def _confirm(self, tool_name: str, arguments: JsonObject) -> bool:
        if not self.settings.confirm_tools:
            return True
        print(f"\nGemini requests tool: {tool_name}")
        print(json.dumps(arguments, ensure_ascii=False, indent=2))
        answer = input("Allow this tool call? [y/N]: ").strip().lower()
        return answer in {"y", "yes", "s", "si", "sí"}

    def call_public_tool(
        self, public_name: str, arguments: JsonObject, confirm: bool = False
    ) -> JsonObject:
        route = self.tool_routes.get(public_name)
        if route is None:
            raise MCPError(f"Unknown tool alias: {public_name}")
        if confirm and not self._confirm(public_name, arguments):
            return {
                "content": [{"type": "text", "text": "User denied the tool call."}],
                "isError": True,
            }
        client, native_name = route
        return client.call_tool(native_name, arguments)

    def chat(self, prompt: str) -> str:
        if not self.settings.gemini_api_key:
            raise GeminiAPIError(
                "GEMINI_API_KEY is missing. Copy .env.example to .env and add your key."
            )
        self.messages.append({"role": "user", "parts": [{"text": prompt}]})
        final_text = ""
        for _ in range(8):
            response = self.gemini.generate_content(self.messages, self.tools)
            content = response["candidates"][0]["content"]
            self.messages.append(content)
            parts = content["parts"]
            text_blocks = [
                part.get("text", "")
                for part in parts
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ]
            final_text = "\n".join(text for text in text_blocks if text)
            tool_uses = [
                part["functionCall"]
                for part in parts
                if isinstance(part, dict) and isinstance(part.get("functionCall"), dict)
            ]
            if not tool_uses:
                return final_text

            tool_results: list[JsonObject] = []
            for tool_use in tool_uses:
                public_name = tool_use.get("name", "")
                arguments = tool_use.get("args", {})
                try:
                    if not isinstance(arguments, dict):
                        raise MCPError("Tool arguments must be a JSON object")
                    result = self.call_public_tool(public_name, arguments, confirm=True)
                    if bool(result.get("isError", False)):
                        function_output: JsonObject = {"error": result}
                    else:
                        function_output = {"result": result}
                except Exception as exc:
                    function_output = {"error": str(exc)}
                function_response: JsonObject = {
                    "name": public_name,
                    "response": function_output,
                }
                call_id = tool_use.get("id")
                if isinstance(call_id, str) and call_id:
                    function_response["id"] = call_id
                tool_results.append({"functionResponse": function_response})
            self.messages.append({"role": "user", "parts": tool_results})
        raise GeminiAPIError("The tool workflow exceeded the limit of 8 model turns")

    def clear_context(self) -> None:
        self.messages.clear()

    def close(self) -> None:
        for client in reversed(list(self.clients.values())):
            client.close()
        self.clients.clear()


HELP = """Commands:
  /tools                  List every discovered MCP tool
  /call TOOL JSON         Call a tool directly (works without an API key)
  /log [N]                Show the last N MCP log entries (default: 10)
  /clear                  Clear the Gemini conversation context
  /help                   Show this help
  /quit                   Exit cleanly
"""


def _show_log(path: Path, count: int) -> None:
    if not path.exists():
        print("No MCP interactions have been logged yet.")
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines[-count:]:
        try:
            print(json.dumps(json.loads(line), ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print(line)


def run_console() -> int:
    settings = Settings.from_environment()
    bot = MCPChatbot(settings)
    print("UVG MCP Network Assistant - manual JSON-RPC/MCP client")
    print(HELP)
    try:
        bot.start_servers()
        print(f"Ready with {len(bot.tools)} tools from {len(bot.clients)} server(s).")
        while True:
            try:
                user_input = input("\nYou> ").strip()
            except EOFError:
                break
            if not user_input:
                continue
            if user_input == "/quit":
                break
            if user_input == "/help":
                print(HELP)
                continue
            if user_input == "/tools":
                for tool in bot.tools:
                    print(f"- {tool['name']}: {tool['description']}")
                continue
            if user_input == "/clear":
                bot.clear_context()
                print("Conversation context cleared.")
                continue
            if user_input.startswith("/log"):
                parts = user_input.split(maxsplit=1)
                try:
                    count = int(parts[1]) if len(parts) == 2 else 10
                except ValueError:
                    print("Usage: /log [positive integer]")
                    continue
                _show_log(settings.log_path, max(1, min(count, 100)))
                continue
            if user_input.startswith("/call "):
                remainder = user_input[len("/call ") :].strip()
                tool_name, separator, raw_json = remainder.partition(" ")
                if not separator:
                    print("Usage: /call TOOL {\"argument\": \"value\"}")
                    continue
                try:
                    arguments = json.loads(raw_json)
                    if not isinstance(arguments, dict):
                        raise ValueError("arguments must be a JSON object")
                    result = bot.call_public_tool(tool_name, arguments)
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                except (json.JSONDecodeError, ValueError, MCPError) as exc:
                    print(f"Tool error: {exc}")
                continue
            try:
                answer = bot.chat(user_input)
                print(f"\nAssistant> {answer}")
            except (GeminiAPIError, MCPError) as exc:
                print(f"\nError: {exc}")
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        bot.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_console())
