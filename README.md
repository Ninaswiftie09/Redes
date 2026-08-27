# Manual MCP Network Assistant

## Author

Nina Nájera Marakovits - 231088

## Overview

This project is a command-line AI host for network operations. It connects the
Google Gemini REST API to local and remote Model Context Protocol (MCP) servers.
The host, MCP clients, custom servers, transports, and JSON-RPC 2.0 exchange are
implemented manually without an MCP SDK.

Implemented features include:

- direct Gemini `generateContent` REST requests with automatic retries for
  transient API failures;
- prompt-aware tool selection that avoids sending unrelated schemas to Gemini;
- conversation context preserved throughout one CLI session;
- visible and persistent logs for every MCP request, response, notification,
  and server diagnostic;
- official Filesystem and Git MCP servers over `stdio`;
- a custom local network-operations MCP server over `stdio`;
- the same custom server deployed on Render over authenticated Streamable HTTP;
- tool discovery and execution through `initialize`,
  `notifications/initialized`, `tools/list`, and `tools/call`;
- Wireshark evidence for the complete remote MCP lifecycle; and
- automated unit and integration coverage for the manual implementations.

## Architecture

```text
User
  |
  v
CLI host (src/chatbot.py) -------- HTTPS --------> Google Gemini API
  |
  +---- JSON-RPC 2.0 / stdio ----> Official Filesystem MCP server
  +---- JSON-RPC 2.0 / stdio ----> Official Git MCP server
  +---- JSON-RPC 2.0 / stdio ----> Local Network Operations MCP server
  +---- JSON-RPC 2.0 / HTTPS ----> Remote Network Operations MCP server
                                      |
                                      +---- Docker container on Render
```

The host creates one client per enabled entry in `mcp_servers.json`. Each client
performs the MCP lifecycle, discovers the server tools, and exposes a unique
alias in the form `SERVER__TOOL`. The remote transport uses MCP Streamable HTTP
in JSON response mode at `POST /mcp` and authenticates with a bearer token.

## Manual protocol implementation

Project code does not import FastMCP or any MCP client/server SDK. The following
behavior is implemented directly:

- JSON-RPC 2.0 request identifiers, results, errors, and notifications;
- MCP protocol negotiation for version `2025-11-25`;
- newline-delimited UTF-8 JSON over local `stdio`;
- Streamable HTTP request and response handling;
- JSON and Server-Sent Event response parsing in the HTTP client;
- required MCP HTTP headers and protocol-version validation;
- bearer authentication, origin validation, and request-size limits; and
- graceful subprocess and HTTP server shutdown.

The official Filesystem and Git servers remain external assignment dependencies;
only the project host and custom server are manual implementations.

## Custom server specification

The custom server supports a corporate help-desk and network-diagnostics use
case. Every tool is read-only.

| Tool | Purpose | Parameters | Main result fields |
| --- | --- | --- | --- |
| `resolve_dns` | Resolve a host during name-resolution troubleshooting | `hostname`; optional `ip_version` (`any`, `ipv4`, `ipv6`) | hostname, address family, unique addresses |
| `check_tcp_connection` | Test whether one application endpoint is reachable | `host`, `port`; optional `timeout_ms` | destination, reachability, elapsed time, error |
| `analyze_cidr` | Calculate IPv4 or IPv6 subnet facts without network traffic | `cidr` | network, prefix, mask, address counts, usable range |
| `get_local_network_info` | Obtain basic host and resolver context | none | hostname, FQDN, visible addresses |

Use DNS and TCP diagnostics only for hosts and networks you are authorized to
test.

### Transports and endpoints

| Mode | Transport | Endpoint or command |
| --- | --- | --- |
| Local | MCP over `stdio` | `python -m src.network_server` |
| Remote | MCP Streamable HTTP over TLS | `POST https://uvg-network-operations.onrender.com/mcp` |
| Health check | HTTPS | `GET https://uvg-network-operations.onrender.com/health` |

`POST /mcp` requires `Authorization: Bearer <token>`. The public health endpoint
does not require authentication and returns the server name and version.

## Requirements

- Windows 10 or later
- Python 3.10 or later
- Node.js 18 or later, including `npm`
- Git
- a Gemini API key for natural-language chatbot prompts
- a Render MCP bearer token for the deployed remote server
- Wireshark only when reproducing the packet analysis

Direct `/call` commands and automated tests do not require a Gemini API key.

## Installation

Open PowerShell in the project directory and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
npm.cmd install
Copy-Item .env.example .env
```

`npm install` installs the official Filesystem server pinned to version
`2025.11.25`. `requirements.txt` installs the official Git server at the same
version and its compatible MCP 1.x dependency.

If PowerShell blocks virtual-environment activation, call its interpreter
directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd install
.\.venv\Scripts\python.exe main.py
```

## Configuration

Copy `.env.example` to `.env`, then set the secrets locally:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.6-flash
MCP_CONFIRM_TOOLS=true
MCP_REQUEST_TIMEOUT=30
MCP_REMOTE_TOKEN=the_same_token_configured_in_render
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `GEMINI_API_KEY` | empty | Secret used for Gemini REST requests |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Gemini model identifier |
| `GEMINI_API_URL` | `https://generativelanguage.googleapis.com` | Gemini REST API base URL |
| `MCP_CONFIRM_TOOLS` | `true` | Confirm every model-requested tool execution |
| `MCP_REQUEST_TIMEOUT` | `30` | MCP response timeout in seconds |
| `MCP_REMOTE_TOKEN` | empty | Bearer token shared with the Render service |

Never commit `.env`, TLS session keys, or authentication headers. `.env` is
excluded by Git and by the container build context.

Local and remote server definitions are stored in `mcp_servers.json`.
`{python}`, `{node}`, `{filesystem_server}`, `{workspace}`, and
`{workspace_posix}` expand at runtime. Filesystem access is restricted to this
repository.

## Run the chatbot

```powershell
python main.py
```

Startup connects every enabled server and prints its initialization and tool
discovery messages. One unavailable server produces a warning without stopping
the remaining clients.

Available commands:

```text
/tools                  list discovered MCP tools
/call TOOL JSON         call a tool directly without Gemini
/log [N]                show the last N MCP log records
/clear                  clear conversation context
/help                   show command help
/quit                   stop every server and exit
```

## Demonstration scenarios

### Local custom server

```text
/call network_ops__analyze_cidr {"cidr":"192.168.50.37/24"}
/call network_ops__resolve_dns {"hostname":"example.com","ip_version":"ipv4"}
/call network_ops__check_tcp_connection {"host":"example.com","port":443,"timeout_ms":2000}
/call network_ops__get_local_network_info {}
```

### Remote custom server

The remote server provides the same interface under the
`network_ops_remote__` prefix:

```text
/call network_ops_remote__analyze_cidr {"cidr":"10.20.30.40/27"}
/call network_ops_remote__resolve_dns {"hostname":"example.com","ip_version":"ipv4"}
```

The console and `logs/mcp.jsonl` show the manual JSON-RPC exchange.

### Conversation context with Gemini

```text
You> Who was Alan Turing?
You> In what year was he born?
```

The second request includes the same session history, allowing Gemini to resolve
the reference to Alan Turing. `/clear` starts a new context.

### Official Filesystem and Git workflow

The verified workflow in `docs/mcp-demo/README.md` was performed through the
chatbot as follows:

1. `filesystem__create_directory` created `docs/mcp-demo`.
2. `filesystem__write_file` created its `README.md`.
3. `git__git_add` staged only that file.
4. `git__git_commit` created commit `a4d3966`.
5. `git__git_status` confirmed the result.

For an interactive demonstration, ask Gemini to create a disposable file,
inspect it, stage it, and commit it. Review every confirmation prompt before
allowing a write or Git operation.

## Remote deployment with Render

The root `render.yaml` defines a free Docker web service named
`uvg-network-operations` on branch `Proyecto1`. To deploy another instance:

1. Open the Render Dashboard and choose **New > Blueprint**.
2. Connect this GitHub repository and select branch `Proyecto1`.
3. Keep the Blueprint path as `render.yaml`.
4. Provide a strong random value for `MCP_AUTH_TOKEN` when prompted.
5. Deploy the Blueprint and wait until the service is `Live`.
6. Store the same value locally as `MCP_REMOTE_TOKEN`.
7. Verify `GET /health`, then run a remote `/call` command.

The Docker image binds to `0.0.0.0` and uses Render's `PORT` environment
variable. Free services can sleep after inactivity, so the first request can be
slower while the instance starts.

## Logs

Every MCP exchange is printed and stored as one JSON object per line in
`logs/mcp.jsonl`. Records contain an ISO-8601 UTC timestamp, server name,
direction, and complete JSON-RPC message. Server `stderr` is logged separately
and never mixed with the protocol `stdout` stream.

Logs can contain tool arguments and results. Review them before sharing and do
not place secrets in tool arguments.

## Wireshark analysis evidence

The screenshots under `docs/capturas` document:

- TCP connection establishment and TLS 1.3 negotiation;
- authenticated HTTPS requests to `POST /mcp`;
- the `initialize` request and response;
- the `notifications/initialized` synchronization notification and HTTP `202`;
- the `tools/list` request and response; and
- a `tools/call` request and successful response.

The packet capture and TLS key log are intentionally excluded from Git because
decrypted HTTP headers include the bearer token. Only reviewed screenshots are
versioned.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The suite covers JSON-RPC validation, tool schemas, network calculations,
notifications, `stdio` lifecycle, Streamable HTTP lifecycle, bearer
authentication, origin and protocol-version validation, SSE parsing, Gemini
tool routing, conversation context, and retry behavior. Tests do not consume
Gemini quota.

## Project structure

```text
main.py                    CLI entry point
mcp_servers.json           local and remote MCP client configuration
render.yaml                Render Blueprint
Dockerfile                 remote server container
src/chatbot.py             host, Gemini REST client, tool loop, and CLI
src/mcp_client.py          manual stdio and Streamable HTTP clients
src/network_server.py      custom JSON-RPC server and network tools
src/remote_server.py       authenticated Streamable HTTP transport
src/config.py              environment and server configuration
tests/                     unit and integration tests
docs/capturas/             reviewed Wireshark evidence
docs/mcp-demo/             official Filesystem and Git MCP demonstration
```

## References

- [MCP specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
- [MCP transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [Official MCP servers](https://github.com/modelcontextprotocol/servers)
- [JSON-RPC 2.0](https://www.jsonrpc.org/specification)
- [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Gemini `generateContent` API](https://ai.google.dev/api/generate-content)
- [Render Blueprints](https://render.com/docs/infrastructure-as-code)
- [Render free services](https://render.com/docs/free)
