"""Minimal MCP 2025-11-25 client implemented directly over JSON-RPC stdio."""

from __future__ import annotations

import json
import queue
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


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
    ) -> None:
        self.name = name
        self.command = command
        self.logger = logger
        self.protocol_version = protocol_version
        self.timeout = timeout
        self.cwd = cwd
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
            {
                "protocolVersion": self.protocol_version,
                # Directory access is supplied to Filesystem on its command line.
                # Advertising roots here would let that server replace the allowlist.
                "capabilities": {},
                "clientInfo": {
                    "name": "uvg-manual-mcp-chatbot",
                    "version": "0.1.0",
                    "description": "CC3067 Project 1 manual MCP client",
                },
            },
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
