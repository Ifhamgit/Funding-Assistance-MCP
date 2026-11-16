# AI Workflow Log (raw notes, condensed into README §4)

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

## 4. Verification — is the concurrency test able to fail? (T7)

- **Concern:** a race test that passes proves nothing unless it fails against a racy implementation.
- **Action:** `tools/mutate_approval_guard.py` rewrites approval as a naive read-check-then-write with no transaction
  (`m1`), and additionally drops the DB CHECK (`m2`). The script runs the race tests and restores the code itself.
- **Observed:**
  - m1 → `IntegrityError: CHECK constraint failed … committed_cents + paid_cents <= allocation_cents`. The race is
    real; the second layer (DB constraint) caught it.
  - m2 → `ValueError: money amounts are never negative`. Available went below zero, i.e. the fund **was overspent**.
  - restored → 125 passed.
- **Correction found by doing this:** the first mutation run reported `not-run` because the thread swallowed non-domain
  exceptions. The harness now records `UNEXPECTED <type>: <message>`, so the failure states its cause.

## 5. Verification — corrections to AI-written test tooling (T7/T8)

- **Line endings:** the first version of `tools/mutate_approval_guard.py` restored files with `write_text`, which on
  Windows rewrote LF as CRLF. Caught by `git status` showing `service.py`/`db.py` modified; `git diff --ignore-cr-at-eol`
  proved it was line endings only. Fix: snapshot and restore exact bytes. Re-verified: after m1 and m2 runs, `git status` is clean.
- **Raw JSON-RPC test:** the first AC-23 test wrote all messages and closed stdin immediately; the reply to the tool call
  never arrived (`KeyError: 2`). The server's stderr showed `tool=list_funds … outcome=ok`, so the server had worked and the
  test harness was wrong (EOF shut the server down before it wrote the reply). Fix: keep stdin open until the reply is read.
- **Environment finding:** `uv run pytest` / `uv run funding-reset` failed with `os error 4551` (Windows Application Control
  blocks uv's generated `.exe` launchers). Commands now use `python -m …` (SPEC changelog 1.1).
