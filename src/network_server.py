"""Industrial network diagnostics MCP server, implemented without an MCP SDK."""

from __future__ import annotations

import ipaddress
import json
import socket
import sys
import time
from typing import Any, Callable


PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "uvg-network-operations"
SERVER_VERSION = "0.1.0"
JsonObject = dict[str, Any]


TOOLS: list[JsonObject] = [
    {
        "name": "resolve_dns",
        "title": "Resolve DNS",
        "description": (
            "Resolve a hostname with the operating system DNS resolver. Use this to "
            "verify name resolution during a corporate connectivity incident. The result "
            "contains unique IP addresses and does not query arbitrary DNS record types."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "DNS hostname or IP literal to resolve.",
                    "minLength": 1,
                    "maxLength": 253,
                },
                "ip_version": {
                    "type": "string",
                    "description": "Address family filter.",
                    "enum": ["any", "ipv4", "ipv6"],
                    "default": "any",
                },
            },
            "required": ["hostname"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    {
        "name": "check_tcp_connection",
        "title": "Check TCP Connection",
        "description": (
            "Attempt a TCP connection to a host and port with a short timeout. Use this "
            "to check whether an application endpoint is reachable; it does not perform "
            "an exhaustive port scan or send application data."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Destination hostname or IP address.",
                    "minLength": 1,
                    "maxLength": 253,
                },
                "port": {
                    "type": "integer",
                    "description": "Destination TCP port from 1 through 65535.",
                    "minimum": 1,
                    "maximum": 65535,
                },
                "timeout_ms": {
                    "type": "integer",
                    "description": "Connection timeout in milliseconds (100-10000).",
                    "minimum": 100,
                    "maximum": 10000,
                    "default": 2000,
                },
            },
            "required": ["host", "port"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    {
        "name": "analyze_cidr",
        "title": "Analyze CIDR Network",
        "description": (
            "Calculate addressing facts for an IPv4 or IPv6 CIDR block locally. Use this "
            "for subnet planning and incident triage. It performs no network traffic."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cidr": {
                    "type": "string",
                    "description": "Network or host with prefix, such as 192.168.10.0/24.",
                    "minLength": 3,
                    "maxLength": 64,
                }
            },
            "required": ["cidr"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "get_local_network_info",
        "title": "Get Local Network Information",
        "description": (
            "Return the local hostname, fully qualified domain name, and addresses visible "
            "through the operating system resolver. Use it as initial context when a "
            "workstation reports a connectivity problem."
        ),
        "inputSchema": {"type": "object", "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
]


def _require_string(arguments: JsonObject, name: str, maximum: int) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{name}' must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"'{name}' exceeds {maximum} characters")
    return value


def resolve_dns(arguments: JsonObject) -> JsonObject:
    hostname = _require_string(arguments, "hostname", 253)
    ip_version = arguments.get("ip_version", "any")
    families = {"any": socket.AF_UNSPEC, "ipv4": socket.AF_INET, "ipv6": socket.AF_INET6}
    if ip_version not in families:
        raise ValueError("'ip_version' must be any, ipv4, or ipv6")
    records = socket.getaddrinfo(hostname, None, families[ip_version], socket.SOCK_STREAM)
    addresses = sorted({record[4][0] for record in records})
    return {"hostname": hostname, "ip_version": ip_version, "addresses": addresses}


def check_tcp_connection(arguments: JsonObject) -> JsonObject:
    host = _require_string(arguments, "host", 253)
    port = arguments.get("port")
    timeout_ms = arguments.get("timeout_ms", 2000)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("'port' must be an integer from 1 through 65535")
    if (
        isinstance(timeout_ms, bool)
        or not isinstance(timeout_ms, int)
        or not 100 <= timeout_ms <= 10000
    ):
        raise ValueError("'timeout_ms' must be an integer from 100 through 10000")

    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout_ms / 1000):
            reachable = True
            error = None
    except OSError as exc:
        reachable = False
        error = str(exc)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "host": host,
        "port": port,
        "reachable": reachable,
        "latency_ms": elapsed_ms,
        "error": error,
    }


def analyze_cidr(arguments: JsonObject) -> JsonObject:
    cidr = _require_string(arguments, "cidr", 64)
    interface = ipaddress.ip_interface(cidr)
    network = interface.network
    result: JsonObject = {
        "input_address": str(interface.ip),
        "ip_version": network.version,
        "network": str(network.network_address),
        "prefix_length": network.prefixlen,
        "netmask": str(network.netmask),
        "total_addresses": network.num_addresses,
        "is_private": network.is_private,
    }
    if network.version == 4:
        result["broadcast"] = str(network.broadcast_address)
        if network.prefixlen <= 30:
            result["first_usable"] = str(network.network_address + 1)
            result["last_usable"] = str(network.broadcast_address - 1)
            result["usable_addresses"] = network.num_addresses - 2
        else:
            result["first_usable"] = str(network.network_address)
            result["last_usable"] = str(network.broadcast_address)
            result["usable_addresses"] = network.num_addresses
    else:
        result["first_address"] = str(network.network_address)
        result["last_address"] = str(network.broadcast_address)
    return result


def get_local_network_info(arguments: JsonObject) -> JsonObject:
    if arguments:
        raise ValueError("get_local_network_info does not accept parameters")
    hostname = socket.gethostname()
    records = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    addresses = sorted({record[4][0] for record in records})
    return {"hostname": hostname, "fqdn": socket.getfqdn(), "addresses": addresses}


HANDLERS: dict[str, Callable[[JsonObject], JsonObject]] = {
    "resolve_dns": resolve_dns,
    "check_tcp_connection": check_tcp_connection,
    "analyze_cidr": analyze_cidr,
    "get_local_network_info": get_local_network_info,
}


def _success(message_id: Any, result: JsonObject) -> JsonObject:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _error(message_id: Any, code: int, message: str) -> JsonObject:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {"code": code, "message": message},
    }


def handle_message(message: Any) -> JsonObject | None:
    """Handle one parsed JSON-RPC request or notification."""

    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid Request")
    method = message.get("method")
    message_id = message.get("id")
    if not isinstance(method, str):
        return _error(message_id, -32600, "Invalid Request")

    if message_id is None:
        return None
    params = message.get("params", {})
    if not isinstance(params, dict):
        return _error(message_id, -32602, "Parameters must be an object")

    if method == "initialize":
        requested_version = params.get("protocolVersion")
        if not isinstance(requested_version, str):
            return _error(message_id, -32602, "protocolVersion is required")
        return _success(
            message_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "title": "UVG Network Operations MCP Server",
                    "version": SERVER_VERSION,
                    "description": "Safe network diagnostics for corporate help desks",
                },
                "instructions": (
                    "Use these read-only diagnostics for authorized hosts and networks only."
                ),
            },
        )
    if method == "ping":
        return _success(message_id, {})
    if method == "tools/list":
        return _success(message_id, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or name not in HANDLERS:
            return _error(message_id, -32602, f"Unknown tool: {name!r}")
        if not isinstance(arguments, dict):
            return _error(message_id, -32602, "Tool arguments must be an object")
        try:
            data = HANDLERS[name](arguments)
            text = json.dumps(data, ensure_ascii=False, indent=2)
            return _success(
                message_id,
                {"content": [{"type": "text", "text": text}], "isError": False},
            )
        except (OSError, ValueError) as exc:
            return _success(
                message_id,
                {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            )
    return _error(message_id, -32601, f"Method not found: {method}")


def main() -> int:
    """Run the newline-delimited stdio transport."""

    print(f"{SERVER_NAME} {SERVER_VERSION} ready on stdio", file=sys.stderr, flush=True)
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_message(request)
        except json.JSONDecodeError:
            response = _error(None, -32700, "Parse error")
        except Exception as exc:  # Keep protocol stream alive after unexpected errors.
            print(f"Unexpected server error: {exc}", file=sys.stderr, flush=True)
            response = _error(None, -32603, "Internal error")
        if response is not None:
            print(
                json.dumps(response, ensure_ascii=False, separators=(",", ":")),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
