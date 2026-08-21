from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from src.config import PROJECT_ROOT
from src.mcp_client import JsonlExchangeLogger, MCPStdioClient


class MCPStdioIntegrationTests(unittest.TestCase):
    def test_manual_client_completes_full_local_server_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            logger = JsonlExchangeLogger(
                Path(temporary_directory) / "mcp.jsonl", display=False
            )
            client = MCPStdioClient(
                name="network_ops_test",
                command=[sys.executable, "-m", "src.network_server"],
                logger=logger,
                cwd=PROJECT_ROOT,
                timeout=5,
            )
            try:
                initialization = client.connect()
                self.assertEqual(initialization["protocolVersion"], "2025-11-25")
                tools = client.list_tools()
                self.assertEqual(len(tools), 4)
                result = client.call_tool("analyze_cidr", {"cidr": "10.20.30.4/28"})
                self.assertFalse(result["isError"])
                self.assertIn("10.20.30.0", result["content"][0]["text"])
            finally:
                client.close()


if __name__ == "__main__":
    unittest.main()
