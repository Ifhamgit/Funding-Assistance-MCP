# AI Workflow Log (raw notes, condensed into README §AI)

Tool: Claude Code (Claude Opus 5.5) in VS Code. Running notes captured during the work, not reconstructed afterwards.

## 1. Requirements analysis / specification

- **Prompt (excerpt):** "first in short and easy tech english explain me what is the problem and what solution we are
  gonna give … take your time to absorb the PDF" → then "check we did not miss anything crucial".
- **AI output:** plain-language summary, then a gap check against the brief. The gaps it found and that went into the spec:
  stored text must not grant permissions (brief says "tool arguments, prompts **and stored text**") → R-04, AC-17;
  participant and fund must belong to the caller's nonprofit → R-03/R-07, AC-14, enforced with composite FKs;
  fixed identity per stdio process means the demo needs one server process per role → §6.1, demo design;
  "implementation methodology" must also say how AI-delegated work is scoped/reviewed → SPEC §8.
- **Correction:** the first summary had missed those points; the second pass, which re-read the brief line by line, caught them.
- **Independent evidence:** each item traced to a sentence in the brief PDF (pages 2–3).

## 2. Implementation planning — SDK version

- **Context:** AI's prior knowledge was the MCP Python SDK v1 (`FastMCP`). `uv add mcp` resolved **mcp 2.3.0**.
- **Correction:** reading `mcp/server/fastmcp.py` showed it is now a stub that raises: *"FastMCP was renamed to MCPServer"*.
  Plan switched to `mcp.server.mcpserver.MCPServer`, `mcp.Client`, `mcp_types` (snake_case fields such as `structured_content`, `is_error`).
- **Evidence:** SDK source in the venv plus a runnable probe (`Annotated[CallToolResult, Model]` gives an output schema; `is_error` results skip output validation).

## 3. Verification — unknown arguments silently ignored

- **Probe:** called a tool with `{"amount": "1.00", "role": "admin"}`.
- **Observed:** `is_error=False` — the SDK's generated argument model silently **ignores** unknown fields.
- **Change:** spec R-04 now requires rejecting unknown arguments (`VALIDATION_ERROR`), tested by AC-16. Silently ignoring a
  `role` argument is harmless today, but rejecting it makes the "arguments cannot grant permissions" rule explicit and testable.
- **Evidence:** probe output recorded during SDK investigation (before T1).
