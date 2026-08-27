"""Manual MCP Streamable HTTP transport for the network operations server."""

from __future__ import annotations

import hmac
import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from src.network_server import (
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    _error,
    handle_message,
)


JsonObject = dict[str, Any]
DEFAULT_ENDPOINT = "/mcp"
DEFAULT_MAX_BODY_BYTES = 64 * 1024


def _integer_environment(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


class MCPHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying configuration shared by request handlers."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        endpoint: str,
        auth_token: str,
        allowed_origins: set[str],
        max_body_bytes: int,
    ) -> None:
        super().__init__(server_address, MCPRequestHandler)
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.allowed_origins = allowed_origins
        self.max_body_bytes = max_body_bytes


class MCPRequestHandler(BaseHTTPRequestHandler):
    """Serve the JSON response mode of MCP Streamable HTTP."""

    server: MCPHTTPServer
    protocol_version = "HTTP/1.1"

    def _write_empty(
        self, status: HTTPStatus, headers: dict[str, str] | None = None
    ) -> None:
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _write_json(
        self,
        status: HTTPStatus,
        payload: JsonObject,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _is_mcp_endpoint(self) -> bool:
        return urlsplit(self.path).path == self.server.endpoint

    def _validate_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None or origin in self.server.allowed_origins:
            return True
        self._write_json(
            HTTPStatus.FORBIDDEN,
            _error(None, -32000, "Origin is not allowed"),
        )
        return False

    def _validate_authorization(self) -> bool:
        expected_token = self.server.auth_token
        if not expected_token:
            return True
        authorization = self.headers.get("Authorization", "")
        expected = f"Bearer {expected_token}"
        if hmac.compare_digest(authorization, expected):
            return True
        self._write_json(
            HTTPStatus.UNAUTHORIZED,
            _error(None, -32001, "Authentication is required"),
            {"WWW-Authenticate": "Bearer"},
        )
        return False

    def _validate_connection(self) -> bool:
        return self._validate_origin() and self._validate_authorization()

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/health":
            self._write_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "server": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            )
            return
        if not self._is_mcp_endpoint():
            self._write_empty(HTTPStatus.NOT_FOUND)
            return
        if not self._validate_connection():
            return
        self._write_empty(HTTPStatus.METHOD_NOT_ALLOWED, {"Allow": "POST"})

    def do_DELETE(self) -> None:
        if not self._is_mcp_endpoint():
            self._write_empty(HTTPStatus.NOT_FOUND)
            return
        if not self._validate_connection():
            return
        self._write_empty(HTTPStatus.METHOD_NOT_ALLOWED, {"Allow": "POST"})

    def do_POST(self) -> None:
        if not self._is_mcp_endpoint():
            self._write_empty(HTTPStatus.NOT_FOUND)
            return
        if not self._validate_connection():
            return

        accept = self.headers.get("Accept", "").lower()
        if "application/json" not in accept or "text/event-stream" not in accept:
            self._write_json(
                HTTPStatus.NOT_ACCEPTABLE,
                _error(None, -32600, "Accept must include JSON and event stream"),
            )
            return
        content_type = self.headers.get("Content-Type", "").lower()
        if not content_type.startswith("application/json"):
            self._write_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                _error(None, -32600, "Content-Type must be application/json"),
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                _error(None, -32700, "Invalid Content-Length"),
            )
            return
        if content_length <= 0 or content_length > self.server.max_body_bytes:
            status = (
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                if content_length > self.server.max_body_bytes
                else HTTPStatus.BAD_REQUEST
            )
            self._write_json(status, _error(None, -32700, "Invalid request body size"))
            return

        raw_body = self.rfile.read(content_length)
        try:
            message = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                _error(None, -32700, "Parse error"),
            )
            return

        method = message.get("method") if isinstance(message, dict) else None
        if method != "initialize":
            requested_version = self.headers.get("MCP-Protocol-Version")
            if requested_version != PROTOCOL_VERSION:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    _error(None, -32600, "Unsupported or missing MCP protocol version"),
                )
                return

        response = handle_message(message)
        if response is None:
            self._write_empty(HTTPStatus.ACCEPTED)
            return
        self._write_json(HTTPStatus.OK, response)

    def log_message(self, message_format: str, *args: object) -> None:
        message = message_format % args
        print(f"[HTTP] {self.address_string()} {message}", file=sys.stderr, flush=True)


def main() -> int:
    """Run the remote transport with settings supplied through the environment."""

    host = os.getenv("MCP_HTTP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = _integer_environment("PORT", 8080)
    endpoint = os.getenv("MCP_ENDPOINT_PATH", DEFAULT_ENDPOINT).strip()
    if not endpoint.startswith("/"):
        raise ValueError("MCP_ENDPOINT_PATH must begin with /")
    auth_token = os.getenv("MCP_AUTH_TOKEN", "").strip()
    allowed_origins = {
        origin.strip()
        for origin in os.getenv("MCP_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    }
    max_body_bytes = _integer_environment(
        "MCP_MAX_BODY_BYTES", DEFAULT_MAX_BODY_BYTES
    )

    server = MCPHTTPServer(
        (host, port),
        endpoint=endpoint,
        auth_token=auth_token,
        allowed_origins=allowed_origins,
        max_body_bytes=max_body_bytes,
    )
    print(
        f"{SERVER_NAME} {SERVER_VERSION} ready on http://{host}:{port}{endpoint}",
        file=sys.stderr,
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
