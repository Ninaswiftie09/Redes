# UVG Manual MCP Network Assistant

A command-line chatbot for **CC3067 Networks - Project 1**. It connects Gemini to
local Model Context Protocol (MCP) servers and implements the MCP client and the
custom server manually with JSON-RPC 2.0. No MCP SDK is imported by the project
code.

The partial-delivery scope is:

- direct connection to the Google Gemini `generateContent` REST API;
- in-session conversation context;
- visible and persistent logs of every MCP request, response, and notification;
- the official Filesystem and Git local MCP servers;
- a custom local MCP server for an industrial network-operations use case;
- the partial report sections 8 and 10.

## Architecture

```text
User
  |
  v
CLI host (src/chatbot.py) ---- HTTPS ----> Google Gemini API
  |
  +---- JSON-RPC 2.0 / stdio ----> Official Filesystem server
  +---- JSON-RPC 2.0 / stdio ----> Official Git server
  +---- JSON-RPC 2.0 / stdio ----> Custom Network Operations server
```

The host starts one subprocess per local server, sends `initialize`, sends the
`notifications/initialized` notification, discovers tools with `tools/list`, and
executes them with `tools/call`. Messages are UTF-8 JSON objects separated by
newlines, as specified by MCP's stdio transport.

## Custom server tools

| Tool | Purpose | Main parameters |
| --- | --- | --- |
| `resolve_dns` | Resolve a hostname for incident triage | `hostname`, optional `ip_version` |
| `check_tcp_connection` | Test whether one TCP endpoint is reachable | `host`, `port`, optional `timeout_ms` |
| `analyze_cidr` | Calculate subnet addressing details locally | `cidr` |
| `get_local_network_info` | Show workstation hostname and resolved addresses | none |

All custom tools are read-only. DNS and TCP tools access only destinations that
the user explicitly supplies. Use them only on systems you are authorized to
diagnose.

## Requirements

- Windows 10 or later (the configuration also resolves `npx.cmd` automatically)
- Python 3.10 or later
- Node.js 18 or later, including `npm` and `npx`
- Git
- A Gemini API key from Google AI Studio for normal chatbot prompts

The direct `/call` command and automated tests do not require an API key.

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

Edit `.env` and replace `replace_with_your_key` with an API key created in
[Google AI Studio](https://aistudio.google.com/app/apikey). The Gemini API has a
Free Tier for supported models, so this project does not require a paid API
account. Do not commit `.env`; it is ignored by Git.

`npm install` installs the official Filesystem server pinned to version
`2025.11.25`. `requirements.txt` installs the official Git server at the same
version and keeps its MCP Python dependency on the compatible 1.x release. Those
packages are required by the assignment; the chatbot and custom server themselves
still implement MCP without an SDK.

If PowerShell blocks virtual-environment activation, use the interpreter
directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd install
.\.venv\Scripts\python.exe main.py
```

## Configuration

`.env` supports these settings:

| Variable | Default | Meaning |
| --- | --- | --- |
| `GEMINI_API_KEY` | empty | Required secret for Gemini requests |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Gemini model ID |
| `GEMINI_API_URL` | `https://generativelanguage.googleapis.com` | Gemini REST API base URL |
| `MCP_CONFIRM_TOOLS` | `true` | Ask before every model-requested tool call |
| `MCP_REQUEST_TIMEOUT` | `30` | MCP response timeout in seconds |

Local subprocess commands are in `mcp_servers.json`. `{python}` expands to the
active Python interpreter, `{node}` resolves the Node.js executable,
`{filesystem_server}` resolves the locally installed official server, and
`{workspace}` expands to this repository's absolute path. Filesystem access is
deliberately limited to that path.

## Run the chatbot

```powershell
python main.py
```

Startup connects each available server and prints all initialization and tool
discovery messages. The CLI continues if one optional server is unavailable, so
the custom server can still be demonstrated while an installation problem is
fixed.

Available commands:

```text
/tools                  list discovered MCP tools
/call TOOL JSON         call a tool without the LLM
/log [N]                show the last N MCP log records
/clear                  clear conversation context
/help                   show command help
/quit                   stop every server and exit
```

## Demonstration scenarios

### 1. Custom local server without an API key

List the exact aliases with `/tools`, then run:

```text
/call network_ops__analyze_cidr {"cidr":"192.168.50.37/24"}
/call network_ops__resolve_dns {"hostname":"example.com","ip_version":"ipv4"}
/call network_ops__check_tcp_connection {"host":"example.com","port":443,"timeout_ms":2000}
/call network_ops__get_local_network_info {}
```

The console displays both the JSON-RPC request and response, and writes them to
`logs/mcp.jsonl`.

### 2. Context with Gemini

```text
You> Who was Alan Turing?
You> In what year was he born?
```

The second answer uses the same Gemini `contents` history. `/clear` starts a new
session.

### 3. Filesystem and Git workflow

Use a disposable directory or branch before demonstrating write operations. Ask:

```text
Create demo-workspace/README.md with a short project description. Then use the
Git tools to show repository status, add that file, and commit it with the message
"docs: add MCP demo readme". Ask for my approval before every tool call.
```

The host presents a confirmation prompt for every model-requested function call. Review the
tool name and arguments before accepting. Git commits also require `user.name` and
`user.email` to be configured in the repository.

## Logs

Every MCP exchange is printed and stored as one JSON object per line in
`logs/mcp.jsonl`. Each entry includes an ISO-8601 UTC timestamp, server name,
direction, and complete message. Server diagnostics from `stderr` are logged too,
but never mixed into the JSON-RPC `stdout` transport.

## Tests

```powershell
python -m unittest discover -v
```

The suite checks request validation, tool schemas, subnet calculations,
notifications, process startup, initialization, discovery, tool execution, and
graceful shutdown. It does not consume Gemini quota or require Internet access.

## Project structure

```text
main.py                    CLI entry point
mcp_servers.json           local server process configuration
src/chatbot.py             host, Gemini REST client, function-calling loop, CLI
src/mcp_client.py          manual MCP/JSON-RPC stdio client and logger
src/network_server.py      manual custom MCP server and network tools
src/config.py              environment and server configuration
tests/                     unit and subprocess integration tests
docs/                      editable report source
output/pdf/                generated partial-delivery report
```

## Current limitations and next delivery

- The included custom server uses local stdio only.
- Remote Streamable HTTP deployment is intentionally deferred.
- Wireshark analysis and report section 9 are intentionally deferred.
- Conversation context is kept in memory for the current process only.
- Network results depend on local DNS, routing, firewall, and endpoint state.

The second delivery should deploy the same custom service remotely, add the
Streamable HTTP transport, capture the exchange in Wireshark, and complete report
sections 8, 9, and 10 with the remote-server findings.

## References

- [MCP specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
- [MCP stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [Official MCP servers](https://github.com/modelcontextprotocol/servers)
- [JSON-RPC 2.0](https://www.jsonrpc.org/specification)
- [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Gemini `generateContent` API](https://ai.google.dev/api/generate-content)
