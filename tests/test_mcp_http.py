from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from src.config import PROJECT_ROOT
from src.mcp_client import JsonlExchangeLogger, MCPStreamableHttpClient
from src.remote_server import MCPHTTPServer


class MCPHTTPIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = MCPHTTPServer(
            ("127.0.0.1", 0),
            endpoint="/mcp",
            auth_token="test-secret",
            allowed_origins={"https://allowed.example"},
            max_body_bytes=64 * 1024,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/mcp"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _post(self, message: dict[str, object], **headers: str):
        request_headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **headers,
        }
        request = urllib.request.Request(
            self.url,
            data=json.dumps(message).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        return urllib.request.urlopen(request, timeout=2)

    def test_manual_http_client_completes_remote_server_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "mcp.jsonl"
            client = MCPStreamableHttpClient(
                name="network_ops_remote_test",
                url=self.url,
                logger=JsonlExchangeLogger(log_path, display=False),
                auth_token="test-secret",
                cwd=PROJECT_ROOT,
                timeout=2,
            )

            initialization = client.connect()
            tools = client.list_tools()
            result = client.call_tool("analyze_cidr", {"cidr": "172.16.8.9/20"})
            client.close()

            self.assertEqual(initialization["protocolVersion"], "2025-11-25")
            self.assertEqual(len(tools), 4)
            self.assertFalse(result["isError"])
            self.assertIn("172.16.0.0", result["content"][0]["text"])
            records = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(
                any(
                    record["message"].get("method") == "notifications/initialized"
                    for record in records
                    if isinstance(record["message"], dict)
                )
            )

    def test_remote_server_requires_bearer_authentication(self) -> None:
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        }

        with self.assertRaises(urllib.error.HTTPError) as context:
            self._post(message)

        self.assertEqual(context.exception.code, 401)
        self.assertEqual(context.exception.headers["WWW-Authenticate"], "Bearer")

    def test_remote_server_rejects_untrusted_origin(self) -> None:
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        }

        with self.assertRaises(urllib.error.HTTPError) as context:
            self._post(
                message,
                Authorization="Bearer test-secret",
                Origin="https://untrusted.example",
            )

        self.assertEqual(context.exception.code, 403)

    def test_remote_server_requires_version_after_initialization(self) -> None:
        message = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}

        with self.assertRaises(urllib.error.HTTPError) as context:
            self._post(message, Authorization="Bearer test-secret")

        self.assertEqual(context.exception.code, 400)

    def test_http_client_parses_sse_json_rpc_events(self) -> None:
        body = (
            b"id: prime\ndata:\n\n"
            b"event: message\n"
            b'data: {"jsonrpc":"2.0","id":7,"result":{}}\n\n'
        )

        messages = MCPStreamableHttpClient._parse_sse(body)

        self.assertEqual(messages, [{"jsonrpc": "2.0", "id": 7, "result": {}}])


if __name__ == "__main__":
    unittest.main()
