# Emergency Assistance Funding — MCP Server

A headless MCP server for a nonprofit's emergency assistance funds. Case workers submit requests, program managers
approve or reject them, and finance records simulated payments. All staff can see committed, paid and available money
per grant fund. The server prevents overspending (including under concurrent approvals), duplicate financial effects,
role violations and cross-nonprofit access.

| Document | Contents |
|---|---|
| [docs/SPEC.md](docs/SPEC.md) | Specification: requirements, state machine, budget rules, data model, MCP tool contracts, permissions, acceptance criteria, task plan, production OAuth, open questions, changelog. Initial version: [v1.0 snapshot](docs/SPEC_v1.0_initial.md) |
| [docs/TRACEABILITY.md](docs/TRACEABILITY.md) | Requirement → implementation → test map |
| [docs/AI_LOG.md](docs/AI_LOG.md) | AI workflow notes, written during the work |

## 1. Setup, run, test

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). Tested on Windows 11 with uv 0.12.9. Dependencies are pinned
in `pyproject.toml` and locked in `uv.lock` (`mcp==2.3.0`, `pydantic==2.14.3`; dev: `pytest==9.2.0`, `ruff==0.14.10`).

```bash
uv sync                                             # install locked dependencies
uv run python -m funding_mcp.seed                   # setup / RESET the database (data/funding.db)
FUNDING_STAFF_ID=stf_cb_case_worker \
  uv run python -m funding_mcp.server               # start the MCP server on stdio
uv run python -m pytest                             # all tests (~35 s)
uv run python -m pytest -m "not e2e and not slow"   # fast subset (~3 s)
uv run python scripts/demo_client.py                # MCP client demo (separate data/demo.db)
uv run python tools/mutate_approval_guard.py m1     # race tests must FAIL against a naive approval
uv run ruff check . && uv run ruff format --check .
```

`funding-reset` and `funding-mcp` also work as short aliases. The `python -m` forms are documented because Windows
Application Control on the development machine blocked uv's generated `.exe` launchers. In PowerShell, set the identity
with `$env:FUNDING_STAFF_ID="stf_cb_case_worker"`.

**Configuration:**
- `FUNDING_STAFF_ID`: the trusted fixture identity for this server process.
- `FUNDING_DB_PATH`: the SQLite file.
- `FUNDING_LOG_LEVEL` / `FUNDING_LOG_FILE`: logging. Logs go to stderr and optionally a file, never stdout.

**Identities:**
- Community Bridge: `stf_cb_case_worker`, `stf_cb_program_manager`, `stf_cb_finance`
- Harbor Aid Collective: `stf_ha_case_worker`, `stf_ha_program_manager`, `stf_ha_finance`

[mcp_config.example.json](mcp_config.example.json) has one MCP client entry per identity.

## 2. Design decisions

- **Layers.** `server.py` adapts MCP to the business layer: schemas, error envelope and argument guard. `service.py` is
  the single policy enforcement point: identity, role, nonprofit scope and business rules. `db.py` holds the SQLite schema
  and transactions. `money.py` handles exact cents.
- **Identity.** The server reads `FUNDING_STAFF_ID` from its launch environment, never from tool input, and resolves it
  to a role and nonprofit in the database on every call. A missing or unknown identity gets `UNAUTHENTICATED`.
- **Nonprofit isolation.** Every query is scoped to the caller's nonprofit, and another nonprofit's record returns the
  same `NOT_FOUND` as a missing one. Composite foreign keys stop the database from storing a request that mixes
  nonprofits. The MCP SDK silently drops unknown arguments, so the server rejects them explicitly: `{"role": ...}` gets a
  `VALIDATION_ERROR`. Stored text is never used to make a decision.
- **Money.** Amounts arrive as decimal strings (`"300.00"`), are converted to integer cents via `Decimal`, and are stored
  as `INTEGER`. `available = allocation − committed − paid`. A database `CHECK` enforces `committed + paid ≤ allocation`.
- **Competing approvals.**
  - Approval runs in `BEGIN IMMEDIATE`, which takes SQLite's write lock up front, so approvals run one after another,
    even across server processes.
  - The reservation itself is one guarded statement,
    `UPDATE funds … WHERE allocation − committed − paid >= amount`. If no row matches, the result is `INSUFFICIENT_FUNDS`.
  - The `CHECK` constraint is a last line of defence.
- **Retries.** Repeating approve, reject or pay on a request already in that state returns `replayed: true` and changes
  nothing. `payments.request_id` is `UNIQUE`. An optional `idempotency_key` on create prevents duplicate submissions.
- **Errors.** Errors return `isError: true` with `{"error": {"code", "message", "details"}}`. The codes are listed in
  SPEC §5.3. Every write runs in one transaction, so a failure leaves state unchanged.

## 3. Verification — actual results (2026-11-16, Windows 11, Python 3.12.10)

| Test file | Covers | Result |
|---|---|---|
| `test_money.py` | cent parsing/formatting, invalid amounts, float drift | 34 passed |
| `test_storage.py` | seed, repeatable reset, DB-level CHECK/FK/UNIQUE guards | 11 passed |
| `test_access.py` | identity, role matrix, cross-nonprofit reads/writes/lists, stored-text injection | 36 passed |
| `test_requests.py` | create, validation, idempotency key, filters, summary totals | 23 passed |
| `test_lifecycle.py` | business-case example, insufficient funds, retries, invalid transitions, invariants | 16 passed |
| `test_concurrency.py` | 2-way race ×25, 20-way race, 6-process race, concurrent duplicate approve/pay | 5 passed |
| `test_e2e_mcp.py` | through MCP over stdio: discovery, 3-identity workflow, missing identity, smuggled args, schema/role/tenant errors, stdout purity | 13 passed |
| **Total** | | **138 passed in 35.8 s** |

**How the concurrency protection was verified:**
- Two $300 approvals race for a $500 fund, repeated 25 times on fresh databases: every round gives exactly one approval
  and one `INSUFFICIENT_FUNDS`.
- A 20-way race approves exactly what fits, and a race across 6 separate processes approves exactly one.
- The tests are proven able to fail: `tools/mutate_approval_guard.py` swaps in a naive check-then-write approval.
  - **m1** (database CHECK kept): the tests fail with `IntegrityError: CHECK constraint failed`.
  - **m2** (CHECK removed too): the fund really overspends and the tests fail.

**Other checks:**
- The demo script passed, ending at paid 300.00, committed 0.00, available 9700.00.
- A fresh clone (`uv sync --locked`, reset, tests, demo, mutations, lint) reproduced all of the above.

**Not run:**
- no real AI client (such as Claude Desktop) was connected; the demo script plays that role;
- no Linux or macOS run;
- no CI or coverage report.

## 4. AI-assisted approach

I worked with Claude Code under the SPEC §8 loop: spec, then failing tests, then code, then verification, one task per
commit. I reviewed every step and checked it against independent evidence. Details are in
[docs/AI_LOG.md](docs/AI_LOG.md).

1. **Requirements.** Prompt: *"check we did not miss anything crucial."* A second, line-by-line pass over the brief found
   points the first summary had missed:
   - stored text must not grant permissions;
   - participant and fund must belong to the caller's nonprofit;
   - stdio means one identity per server process;
   - the methodology must cover reviewing AI-delegated work.

   Each became a requirement plus a test. *Evidence:* the matching sentences in the brief.
2. **Implementation planning.** The AI expected MCP SDK v1 (`FastMCP`), but version 2.3.0 was installed. Reading the
   installed source showed the rename to `MCPServer`. A short probe then showed the SDK silently ignores unknown
   arguments, which became R-04 and AC-16. *Evidence:* the SDK source and probe output, before any code.
3. **Verification.** The mutation check above. Corrections along the way:
   - the race harness swallowed thread errors, so it now reports their cause;
   - the mutation tool's restore rewrote line endings, caught by `git status`;
   - a raw JSON-RPC test closed stdin too early. The server's own log line (`outcome=ok`) showed the test was wrong, not
     the server.

## 5. Spec revisions

v1.0 was committed before any code (`fc49712`). The v1.1 changes are listed in SPEC §12 with reasons:
- concurrent-retry criteria;
- unknown-tool-name behavior;
- a concrete stdout-purity test;
- `python -m` commands.

No business rule changed.

## 6. Time spent

**About 1 h 40 min in total**, under the 3-hour limit:

| Phase | Time |
|---|---|
| Reading the brief, requirements analysis, gap check with AI | ~25 min |
| AI-assisted build: spec v1.0 and tasks T1–T9 (commit timestamps 18:44 → 19:05 in `git log`, SDK investigation before that) | ~45 min |
| My own review and verification: reading spec and code, tracing requirements, running the demo and tests, README edits | ~30 min |

## 7. Limitations and next priorities

**Limitations:**
- The fixture identity comes from an environment variable. That is fine for local stdio but not for production; SPEC §10
  covers OAuth.
- SQLite allows a single writer.
- `list_requests` has no pagination.
- There is no separate audit-event table.
- Approved-but-unpaid money stays committed, because cancellation is out of scope (SPEC A-7).

**Next priorities:**
1. HTTP transport with OAuth token validation and membership mapping (SPEC §10).
2. An append-only audit log.
3. Ask the business the SPEC §11 questions: approval thresholds, fund purpose restrictions and releasing stale approvals.
4. CI on Linux and Windows.
5. Pagination.
