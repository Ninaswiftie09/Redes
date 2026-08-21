from __future__ import annotations

import unittest

from src.network_server import PROTOCOL_VERSION, handle_message


class NetworkServerUnitTests(unittest.TestCase):
    def test_initialize_advertises_expected_protocol_and_tools(self) -> None:
        response = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            }
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["result"]["protocolVersion"], "2025-11-25")
        self.assertIn("tools", response["result"]["capabilities"])

    def test_tools_list_exposes_four_industry_tools(self) -> None:
        response = handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )

        assert response is not None
        names = {tool["name"] for tool in response["result"]["tools"]}
        self.assertEqual(
            names,
            {
                "resolve_dns",
                "check_tcp_connection",
                "analyze_cidr",
                "get_local_network_info",
            },
        )

    def test_analyze_cidr_returns_expected_subnet_data(self) -> None:
        response = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "analyze_cidr",
                    "arguments": {"cidr": "192.168.10.55/24"},
                },
            }
        )

        assert response is not None
        result = response["result"]
        self.assertFalse(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn('"network": "192.168.10.0"', text)
        self.assertIn('"usable_addresses": 254', text)

    def test_invalid_tool_argument_is_a_tool_error_not_protocol_crash(self) -> None:
        response = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "check_tcp_connection",
                    "arguments": {"host": "localhost", "port": 70000},
                },
            }
        )

        assert response is not None
        self.assertTrue(response["result"]["isError"])
        self.assertIn("65535", response["result"]["content"][0]["text"])

    def test_notification_has_no_response(self) -> None:
        response = handle_message(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        self.assertIsNone(response)


if __name__ == "__main__":
    unittest.main()
