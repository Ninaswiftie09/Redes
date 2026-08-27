from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.chatbot import GeminiGenerateContentClient, MCPChatbot
from src.config import PROJECT_ROOT, Settings


class FakeGeminiClient:
    def __init__(self, responses: list[dict[str, object]] | None = None) -> None:
        self.calls: list[list[dict[str, object]]] = []
        self.tool_calls: list[list[dict[str, object]]] = []
        self.responses = responses or []

    def generate_content(self, contents, tools):  # type: ignore[no-untyped-def]
        self.calls.append(copy.deepcopy(contents))
        self.tool_calls.append(copy.deepcopy(tools))
        answer_number = len(self.calls)
        if self.responses:
            return self.responses.pop(0)
        return {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": f"answer {answer_number}"}],
                    }
                }
            ]
        }


class FakeMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call_tool(self, name, arguments):  # type: ignore[no-untyped-def]
        self.calls.append((name, copy.deepcopy(arguments)))
        return {
            "content": [{"type": "text", "text": '{"network":"10.0.0.0"}'}],
            "isError": False,
        }


class GeminiClientRetryTests(unittest.TestCase):
    @patch("src.chatbot.time.sleep")
    @patch("src.chatbot.urllib.request.urlopen")
    def test_transient_http_error_is_retried(self, urlopen, sleep) -> None:
        unavailable = urllib.error.HTTPError(
            "https://example.invalid",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b'{"error":"busy"}'),
        )
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": "OK"}],
                        }
                    }
                ]
            }
        ).encode("utf-8")
        urlopen.side_effect = [unavailable, response]
        client = GeminiGenerateContentClient(
            "test-key", "test-model", "https://example.invalid"
        )

        result = client.generate_content(
            [{"role": "user", "parts": [{"text": "test"}]}], []
        )

        self.assertEqual(result["candidates"][0]["content"]["parts"][0]["text"], "OK")
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(1)


class ChatbotContextTests(unittest.TestCase):
    def test_general_question_does_not_send_unrelated_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings = Settings(
                gemini_api_key="test-key",
                gemini_model="test-model",
                gemini_base_url="https://example.invalid",
                mcp_protocol_version="2025-11-25",
                request_timeout=2,
                confirm_tools=False,
                log_path=Path(temporary_directory) / "mcp.jsonl",
                server_config_path=PROJECT_ROOT / "mcp_servers.json",
            )
            bot = MCPChatbot(settings)
            bot.tools = [
                {
                    "name": "network_ops_remote__analyze_cidr",
                    "description": "Analyze a CIDR network.",
                    "parametersJsonSchema": {"type": "object"},
                }
            ]
            fake = FakeGeminiClient()
            bot.gemini = fake  # type: ignore[assignment]

            bot.chat("Who was Alan Turing?")

            self.assertEqual(fake.tool_calls, [[]])

    def test_explicit_alias_sends_only_the_named_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings = Settings(
                gemini_api_key="test-key",
                gemini_model="test-model",
                gemini_base_url="https://example.invalid",
                mcp_protocol_version="2025-11-25",
                request_timeout=2,
                confirm_tools=False,
                log_path=Path(temporary_directory) / "mcp.jsonl",
                server_config_path=PROJECT_ROOT / "mcp_servers.json",
            )
            bot = MCPChatbot(settings)
            bot.tools = [
                {
                    "name": "network_ops__analyze_cidr",
                    "description": "Analyze a CIDR network locally.",
                    "parametersJsonSchema": {"type": "object"},
                },
                {
                    "name": "network_ops_remote__analyze_cidr",
                    "description": "Analyze a CIDR network remotely.",
                    "parametersJsonSchema": {"type": "object"},
                },
            ]
            fake = FakeGeminiClient()
            bot.gemini = fake  # type: ignore[assignment]

            bot.chat("Use network_ops_remote__analyze_cidr for this request.")

            self.assertEqual(
                [tool["name"] for tool in fake.tool_calls[0]],
                ["network_ops_remote__analyze_cidr"],
            )

    def test_two_prompts_share_the_same_session_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings = Settings(
                gemini_api_key="test-key",
                gemini_model="test-model",
                gemini_base_url="https://example.invalid",
                mcp_protocol_version="2025-11-25",
                request_timeout=2,
                confirm_tools=False,
                log_path=Path(temporary_directory) / "mcp.jsonl",
                server_config_path=PROJECT_ROOT / "mcp_servers.json",
            )
            bot = MCPChatbot(settings)
            fake = FakeGeminiClient()
            bot.gemini = fake  # type: ignore[assignment]

            self.assertEqual(bot.chat("Who was Alan Turing?"), "answer 1")
            self.assertEqual(bot.chat("When was he born?"), "answer 2")

            second_request = fake.calls[1]
            self.assertEqual(
                [message["role"] for message in second_request],
                ["user", "model", "user"],
            )
            self.assertEqual(
                second_request[0]["parts"], [{"text": "Who was Alan Turing?"}]
            )
            self.assertEqual(
                second_request[2]["parts"], [{"text": "When was he born?"}]
            )

    def test_function_call_is_executed_through_mcp_and_returned_to_gemini(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings = Settings(
                gemini_api_key="test-key",
                gemini_model="test-model",
                gemini_base_url="https://example.invalid",
                mcp_protocol_version="2025-11-25",
                request_timeout=2,
                confirm_tools=False,
                log_path=Path(temporary_directory) / "mcp.jsonl",
                server_config_path=PROJECT_ROOT / "mcp_servers.json",
            )
            bot = MCPChatbot(settings)
            fake_gemini = FakeGeminiClient(
                responses=[
                    {
                        "candidates": [
                            {
                                "content": {
                                    "role": "model",
                                    "parts": [
                                        {
                                            "functionCall": {
                                                "id": "call-1",
                                                "name": "network_ops__analyze_cidr",
                                                "args": {"cidr": "10.0.0.8/24"},
                                            }
                                        }
                                    ],
                                }
                            }
                        ]
                    },
                    {
                        "candidates": [
                            {
                                "content": {
                                    "role": "model",
                                    "parts": [{"text": "The network is 10.0.0.0/24."}],
                                }
                            }
                        ]
                    },
                ]
            )
            fake_mcp = FakeMCPClient()
            bot.gemini = fake_gemini  # type: ignore[assignment]
            bot.tool_routes["network_ops__analyze_cidr"] = (
                fake_mcp,  # type: ignore[arg-type]
                "analyze_cidr",
            )

            answer = bot.chat("Analyze 10.0.0.8/24")

            self.assertEqual(answer, "The network is 10.0.0.0/24.")
            self.assertEqual(
                fake_mcp.calls, [("analyze_cidr", {"cidr": "10.0.0.8/24"})]
            )
            function_response = fake_gemini.calls[1][-1]["parts"][0][
                "functionResponse"
            ]
            self.assertEqual(function_response["id"], "call-1")
            self.assertIn("result", function_response["response"])


if __name__ == "__main__":
    unittest.main()
