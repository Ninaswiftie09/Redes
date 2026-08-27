"""Minimal MCP 2025-11-25 clients implemented directly over JSON-RPC."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any, Protocol, TextIO
from urllib.parse import urlsplit


JsonObject = dict[str, Any]


class JsonlExchangeLogger:
    """Persist and display every JSON-RPC exchange with MCP servers."""

    def __init__(self, path: Path, display: bool = True) -> None:
        self.path = path
        self.display = display
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, server: str, direction: str, message: Any) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server": server,
            "direction": direction,
            "message": message,
        }
        serialized = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            with self.path.open("a", encoding="utf-8") as log_file:
                log_file.write(serialized + "\n")
        if self.display:
            preview = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
            print(f"[MCP][{server}][{direction.upper()}] {preview}")


class MCPError(RuntimeError):
    """Raised when an MCP server returns a JSON-RPC error or becomes unavailable."""


class MCPClient(Protocol):
    """Operations the chatbot requires from any MCP transport."""

    name: str

    def connect(self) -> JsonObject: ...

    def list_tools(self) -> list[JsonObject]: ...

    def call_tool(self, name: str, arguments: JsonObject) -> JsonObject: ...

    def close(self) -> None: ...


def _initialization_parameters(protocol_version: str) -> JsonObject:
    return {
        "protocolVersion": protocol_version,
        "capabilities": {},
        "clientInfo": {
            "name": "uvg-manual-mcp-chatbot",
            "version": "0.1.0",
            "description": "CC3067 Project 1 manual MCP client",
        },
    }


class MCPStdioClient:
    """Manage one MCP server process and exchange newline-delimited JSON-RPC."""

    def __init__(
        self,
        name: str,
        command: list[str],
        logger: JsonlExchangeLogger,
        protocol_version: str = "2025-11-25",
        timeout: float = 30.0,
        cwd: Path | None = None,
        environment: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.command = command
        self.logger = logger
        self.protocol_version = protocol_version
        self.timeout = timeout
        self.cwd = cwd
        self.environment = environment or {}
        self.process: subprocess.Popen[str] | None = None
        self.server_info: JsonObject = {}
        self._next_id = 1
        self._id_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._pending: dict[int | str, queue.Queue[JsonObject]] = {}
        self._pending_lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None

    def connect(self) -> JsonObject:
        """Launch the subprocess and perform the required MCP initialization phase."""

        if self.process is not None:
            return self.server_info
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=str(self.cwd) if self.cwd else None,
                env={**os.environ, **self.environment},
            )
        except OSError as exc:
            raise MCPError(f"Could not start server '{self.name}': {exc}") from exc

        assert self.process.stdout is not None
        assert self.process.stderr is not None
        self._reader_thread = threading.Thread(
            target=self._read_stdout,
            args=(self.process.stdout,),
            name=f"mcp-{self.name}-stdout",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            args=(self.process.stderr,),
            name=f"mcp-{self.name}-stderr",
            daemon=True,
        )
        self._reader_thread.start()
        self._stderr_thread.start()

        result = self.request(
            "initialize",
            _initialization_parameters(self.protocol_version),
        )
        negotiated = result.get("protocolVersion")
        if negotiated != self.protocol_version:
            self.close()
            raise MCPError(
                f"Server '{self.name}' negotiated unsupported version {negotiated!r}"
            )
        self.server_info = result.get("serverInfo", {})
        self.notify("notifications/initialized")
        return result

    def _read_stdout(self, stream: TextIO) -> None:
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message: JsonObject = json.loads(line)
            except json.JSONDecodeError:
                self.logger.record(self.name, "invalid-json", line)
                continue
            self.logger.record(self.name, "received", message)

            message_id = message.get("id")
            if message_id is not None and ("result" in message or "error" in message):
                with self._pending_lock:
                    waiter = self._pending.get(message_id)
                if waiter is not None:
                    waiter.put(message)
                continue
            if message_id is not None and "method" in message:
                self._handle_server_request(message)

    def _read_stderr(self, stream: TextIO) -> None:
        for raw_line in stream:
            line = raw_line.rstrip()
            if line:
                self.logger.record(self.name, "stderr", line)

    def _handle_server_request(self, message: JsonObject) -> None:
        method = message.get("method")
        message_id = message["id"]
        if method == "roots/list" and self.cwd is not None:
            response: JsonObject = {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "roots": [
                        {"uri": self.cwd.resolve().as_uri(), "name": self.cwd.name}
                    ]
                },
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {"code": -32601, "message": f"Method not supported: {method}"},
            }
        self._send(response)

    def _new_id(self) -> int:
        with self._id_lock:
            request_id = self._next_id
            self._next_id += 1
            return request_id

    def _send(self, message: JsonObject) -> None:
        process = self.process
        if process is None or process.stdin is None or process.poll() is not None:
            raise MCPError(f"Server '{self.name}' is not running")
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        with self._write_lock:
            try:
                process.stdin.write(payload + "\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise MCPError(f"Lost connection to server '{self.name}'") from exc
        self.logger.record(self.name, "sent", message)

    def request(self, method: str, params: JsonObject | None = None) -> JsonObject:
        request_id = self._new_id()
        waiter: queue.Queue[JsonObject] = queue.Queue(maxsize=1)
        with self._pending_lock:
            self._pending[request_id] = waiter
        message: JsonObject = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        try:
            self._send(message)
            try:
                response = waiter.get(timeout=self.timeout)
            except queue.Empty as exc:
                self.notify("notifications/cancelled", {"requestId": request_id})
                raise MCPError(
                    f"Timed out waiting for '{method}' from server '{self.name}'"
                ) from exc
        finally:
            with self._pending_lock:
                self._pending.pop(request_id, None)

        if "error" in response:
            error = response["error"]
            raise MCPError(
                f"Server '{self.name}' returned {error.get('code')}: {error.get('message')}"
            )
        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPError(f"Server '{self.name}' returned a non-object result")
        return result

    def notify(self, method: str, params: JsonObject | None = None) -> None:
        message: JsonObject = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def list_tools(self) -> list[JsonObject]:
        tools: list[JsonObject] = []
        cursor: str | None = None
        while True:
            params = {"cursor": cursor} if cursor else None
            result = self.request("tools/list", params)
            page = result.get("tools", [])
            if not isinstance(page, list):
                raise MCPError(f"Server '{self.name}' returned an invalid tools list")
            tools.extend(tool for tool in page if isinstance(tool, dict))
            cursor = result.get("nextCursor")
            if not cursor:
                return tools

    def call_tool(self, name: str, arguments: JsonObject) -> JsonObject:
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        process = self.process
        self.process = None
        if process is None:
            return
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass

    def __enter__(self) -> "MCPStdioClient":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class MCPStreamableHttpClient:
    """Exchange MCP JSON-RPC messages through Streamable HTTP."""

    def __init__(
        self,
        name: str,
        url: str,
        logger: JsonlExchangeLogger,
        protocol_version: str = "2025-11-25",
        timeout: float = 30.0,
        auth_token: str = "",
        cwd: Path | None = None,
    ) -> None:
        parsed_url = urlsplit(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError(f"Invalid MCP HTTP URL: {url!r}")
        self.name = name
        self.url = url
        self.logger = logger
        self.protocol_version = protocol_version
        self.timeout = timeout
        self.auth_token = auth_token
        self.cwd = cwd
        self.server_info: JsonObject = {}
        self.session_id = ""
        self._next_id = 1
        self._connected = False
        self._initialization: JsonObject | None = None

    def _new_id(self) -> int:
        request_id = self._next_id
        self._next_id += 1
        return request_id

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json; charset=utf-8",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if self._connected:
            headers["MCP-Protocol-Version"] = self.protocol_version
        if self.session_id:
            headers["MCP-Session-Id"] = self.session_id
        return headers

    @staticmethod
    def _parse_sse(body: bytes) -> list[JsonObject]:
        messages: list[JsonObject] = []
        data_lines: list[str] = []
        text = body.decode("utf-8")
        for line in [*text.splitlines(), ""]:
            if line == "":
                if data_lines:
                    payload = "\n".join(data_lines)
                    data_lines.clear()
                    if payload:
                        message = json.loads(payload)
                        if not isinstance(message, dict):
                            raise MCPError("MCP SSE event did not contain a JSON object")
                        messages.append(message)
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        return messages

    def _server_request_response(self, message: JsonObject) -> JsonObject:
        method = message.get("method")
        message_id = message["id"]
        if method == "roots/list" and self.cwd is not None:
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "roots": [
                        {"uri": self.cwd.resolve().as_uri(), "name": self.cwd.name}
                    ]
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {"code": -32601, "message": f"Method not supported: {method}"},
        }

    def _send_message(self, message: JsonObject) -> list[JsonObject]:
        payload = json.dumps(
            message, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=payload,
            headers=self._headers(),
            method="POST",
        )
        self.logger.record(self.name, "sent", message)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = response.status
                content_type = response.headers.get_content_type()
                session_id = response.headers.get("MCP-Session-Id", "").strip()
                body = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise MCPError(
                f"Server '{self.name}' returned HTTP {exc.code}: {body}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise MCPError(f"Could not reach server '{self.name}': {exc}") from exc

        if session_id:
            self.session_id = session_id
        if status == 202:
            if body:
                raise MCPError(
                    f"Server '{self.name}' returned a body for an accepted notification"
                )
            return []
        if status != 200:
            raise MCPError(f"Server '{self.name}' returned unexpected HTTP {status}")
        try:
            if content_type == "application/json":
                message_body = json.loads(body.decode("utf-8"))
                if not isinstance(message_body, dict):
                    raise MCPError("MCP HTTP response did not contain a JSON object")
                messages = [message_body]
            elif content_type == "text/event-stream":
                messages = self._parse_sse(body)
            else:
                raise MCPError(
                    f"Server '{self.name}' returned unsupported content type "
                    f"{content_type!r}"
                )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MCPError(
                f"Server '{self.name}' returned invalid JSON over HTTP"
            ) from exc
        for received in messages:
            self.logger.record(self.name, "received", received)
        return messages

    def _exchange(self, message: JsonObject) -> JsonObject:
        expected_id = message["id"]
        messages = self._send_message(message)
        response: JsonObject | None = None
        for received in messages:
            if received.get("id") == expected_id and (
                "result" in received or "error" in received
            ):
                response = received
                continue
            if received.get("id") is not None and isinstance(
                received.get("method"), str
            ):
                self._send_message(self._server_request_response(received))
        if response is None:
            raise MCPError(
                f"Server '{self.name}' did not return a response for request {expected_id}"
            )
        return response

    def connect(self) -> JsonObject:
        if self._initialization is not None:
            return self._initialization
        result = self.request(
            "initialize", _initialization_parameters(self.protocol_version)
        )
        negotiated = result.get("protocolVersion")
        if negotiated != self.protocol_version:
            self.close()
            raise MCPError(
                f"Server '{self.name}' negotiated unsupported version {negotiated!r}"
            )
        self.server_info = result.get("serverInfo", {})
        self._connected = True
        self._initialization = result
        self.notify("notifications/initialized")
        return result

    def request(self, method: str, params: JsonObject | None = None) -> JsonObject:
        message: JsonObject = {
            "jsonrpc": "2.0",
            "id": self._new_id(),
            "method": method,
        }
        if params is not None:
            message["params"] = params
        response = self._exchange(message)
        if "error" in response:
            error = response["error"]
            raise MCPError(
                f"Server '{self.name}' returned {error.get('code')}: "
                f"{error.get('message')}"
            )
        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPError(f"Server '{self.name}' returned a non-object result")
        return result

    def notify(self, method: str, params: JsonObject | None = None) -> None:
        message: JsonObject = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        responses = self._send_message(message)
        if responses:
            raise MCPError(f"Server '{self.name}' responded to a notification")

    def list_tools(self) -> list[JsonObject]:
        tools: list[JsonObject] = []
        cursor: str | None = None
        while True:
            params = {"cursor": cursor} if cursor else None
            result = self.request("tools/list", params)
            page = result.get("tools", [])
            if not isinstance(page, list):
                raise MCPError(f"Server '{self.name}' returned an invalid tools list")
            tools.extend(tool for tool in page if isinstance(tool, dict))
            cursor = result.get("nextCursor")
            if not cursor:
                return tools

    def call_tool(self, name: str, arguments: JsonObject) -> JsonObject:
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        session_id = self.session_id
        headers = self._headers()
        self.session_id = ""
        self._connected = False
        self._initialization = None
        if not session_id:
            return
        request = urllib.request.Request(self.url, headers=headers, method="DELETE")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout):
                pass
        except urllib.error.HTTPError as exc:
            if exc.code != HTTPStatus.METHOD_NOT_ALLOWED:
                raise MCPError(
                    f"Could not close session for server '{self.name}': HTTP {exc.code}"
                ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise MCPError(
                f"Could not close session for server '{self.name}': {exc}"
            ) from exc
