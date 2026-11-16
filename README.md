# Emergency Assistance Funding — MCP Server

A headless MCP server for a nonprofit's emergency assistance funds. Case workers submit requests, program managers
approve or reject them, and finance records simulated payments. Every staff member can see what is committed, paid
and available per grant fund. Built spec-first and test-first.
The server prevents overspending (even under concurrent approvals), duplicate financial effects, role violations and
cross-nonprofit access.

| Document | Contents |
|---|---|
| [docs/SPEC.md](docs/SPEC.md) (initial: [v1.0 snapshot](docs/SPEC_v1.0_initial.md)) | **Specification**: requirements R-01..R-25, state machine, budget rules, data model, MCP tool contracts, permissions, acceptance criteria AC-01..AC-25, task plan + gates, production OAuth design, open questions, **changelog** |
| [docs/TRACEABILITY.md](docs/TRACEABILITY.md) | Requirement → implementation → test map |
| [docs/AI_LOG.md](docs/AI_LOG.md) | Raw AI-workflow notes, taken while working |
| `git log` | Spec v1.0 committed first (`fc49712`), then one commit per task T1–T9 |

## 1. Setup, run, test

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/) (tested with uv 0.12.9 on Windows 11). Dependencies are pinned
exactly in `pyproject.toml` and fully locked in `uv.lock` (`mcp==2.3.0`, `pydantic==2.14.3`; dev: `pytest==9.2.0`, `ruff==0.14.10`).

```bash
uv sync                                         # install locked dependencies
uv run python -m funding_mcp.seed               # setup / RESET database -> data/funding.db   (alias: uv run funding-reset)
FUNDING_STAFF_ID=stf_cb_case_worker \
  uv run python -m funding_mcp.server           # start the MCP server on stdio              (alias: uv run funding-mcp)
uv run python -m pytest                         # all 138 tests (~35 s)
uv run python -m pytest -m "not e2e and not slow"   # fast subset (~3 s)
uv run python scripts/demo_client.py            # MCP client demo (uses its own data/demo.db)
uv run python tools/mutate_approval_guard.py m1 # mutation check: race tests must FAIL against a naive approval
uv run ruff check . && uv run ruff format --check .
```

PowerShell: `$env:FUNDING_STAFF_ID="stf_cb_case_worker"; uv run python -m funding_mcp.server`. Use the `python -m` forms.
On the development machine, Windows Application Control blocked uv's generated `.exe` shims (`os error 4551`).

| Env var | Meaning |
|---|---|
| `FUNDING_STAFF_ID` | **Trusted fixture identity** for this server process (required for every call) |
| `FUNDING_DB_PATH` | SQLite file (default `data/funding.db`) |
| `FUNDING_LOG_LEVEL` / `FUNDING_LOG_FILE` | Logging (stderr always; file optional). Nothing is ever logged to stdout |

Fixture identities (seed data, SPEC §9). Community Bridge: `stf_cb_case_worker`, `stf_cb_program_manager`,
`stf_cb_finance`. Harbor Aid Collective: `stf_ha_case_worker`, `stf_ha_program_manager`, `stf_ha_finance`.
**MCP client config:** [mcp_config.example.json](mcp_config.example.json) has one server entry per identity
(set `ABSOLUTE_PATH`).

## 2. Design in brief

**Layers.** `server.py` adapts MCP to the business layer: schemas, the error envelope and an argument guard.
`service.py` is the **single policy enforcement point**: identity, role, nonprofit scope and business rules.
`db.py` holds the SQLite schema and transactions. `money.py` handles exact cents.

**Identity and permissions.** The server reads `FUNDING_STAFF_ID` from its launch environment, never from tool input.
It resolves that ID in the `staff` table on **every** call and gets the role and nonprofit from there. Missing or unknown
identities get `UNAUTHENTICATED`. All queries are scoped by the caller's `nonprofit_id`. Another nonprofit's record returns
the same `NOT_FOUND` as a missing record, so callers can't even probe whether it exists. Composite foreign keys stop the
database from ever storing a request whose participant or fund belongs to a different nonprofit.

The SDK's generated argument model **silently drops unknown arguments**, which we found with a probe. The server therefore
rejects them explicitly, so `{"role": "program_manager"}` in a call gets a `VALIDATION_ERROR` instead of being quietly
ignored. Stored text (descriptions, reasons) is only ever data.

**Money.** Amounts come in as decimal strings (`"300.00"`, at most 2 decimals, regex-checked), are converted to integer
cents through `Decimal`, and are stored as `INTEGER`. Responses give `{cents, usd}`. Floats never touch money.
`available = allocation − committed − paid`, and a database `CHECK` constraint enforces
`committed + paid ≤ allocation`.

**Competing approvals (R-17).** There are three layers of protection:
1. Approval runs inside `BEGIN IMMEDIATE`, which takes SQLite's single write lock before reading, so concurrent
   approvals, even from different server processes, run one after another.
2. The reservation is a guarded update,
   `UPDATE funds SET committed = committed + A WHERE … AND allocation − committed − paid >= A`. If no row is updated, the
   result is `INSUFFICIENT_FUNDS`. The check and the write are a single statement, so this stays correct even on a
   database with weaker isolation.
3. The `CHECK` constraint rejects any overspend that slips past the application code.

**How the protection was verified:**
- Threads with separate connections race two 300.00 approvals for a 500.00 fund, 25 rounds on fresh databases. Every
  round gives exactly one approval and one `INSUFFICIENT_FUNDS`.
- A 20-way race (20 × 50.00 on 500.00) approves exactly 10.
- The same race across **6 OS processes** approves exactly one.
- 8 concurrent approvals of the *same* request, and 8 concurrent payments of one request, each produce one effect and
  7 replays.
- **Mutation check** (`tools/mutate_approval_guard.py`): with approval rewritten as a naive check-then-write, the tests
  fail. With the CHECK constraint kept (m1) they fail with `IntegrityError: CHECK constraint failed`. With it removed too
  (m2) the fund really overspends and they fail with `ValueError: money amounts are never negative`.

**Retries (R-14).** Repeating an action on a request that is already in that action's target state succeeds with
`replayed: true` and changes nothing. A payment retry returns the original payment, and `payments.request_id` is
`UNIQUE` at the database level. `create_assistance_request` accepts an optional `idempotency_key`: the same key with the
same payload returns the original request, and the same key with a different payload returns `IDEMPOTENCY_CONFLICT`.

**Errors.** `isError: true` with `{"error": {"code", "message", "details"}}` in both `structuredContent` and the text
content. The codes are `UNAUTHENTICATED`, `VALIDATION_ERROR`, `FORBIDDEN`, `NOT_FOUND`, `INVALID_TRANSITION`,
`INSUFFICIENT_FUNDS`, `IDEMPOTENCY_CONFLICT` and `INTERNAL_ERROR`. Every write runs in one transaction, so any failure
leaves state unchanged; the tests compare full table snapshots before and after.

## 3. Verification — actual results (2026-11-16, Windows 11, Python 3.12.10)

| Test file | What it covers | Result |
|---|---|---|
| `test_money.py` | cent parsing/formatting, invalid amounts, float drift | 34 passed |
| `test_storage.py` | seed, repeatable reset, DB-level CHECK/FK/UNIQUE guards, reset CLI | 11 passed |
| `test_access.py` | identity, role matrix, cross-nonprofit reads/writes/lists, stored-text injection | 36 passed |
| `test_requests.py` | create, validation, idempotency key, list filters, summary totals | 23 passed |
| `test_lifecycle.py` | business-case example, insufficient funds, exact remainder, retries, invalid transitions, invariants | 16 passed |
| `test_concurrency.py` | 2-way ×25, 20-way, cross-process, concurrent duplicate approve/pay | 5 passed |
| `test_e2e_mcp.py` | **through MCP over stdio**: discovery + schemas, full workflow with 3 identities, missing identity, smuggled role args, schema errors, role/tenant errors, raw JSON-RPC stdout purity, startup without DB | 13 passed |
| **Total** `uv run python -m pytest` | | **138 passed in 35.8 s** |

The demo (`scripts/demo_client.py`) passed with final `paid 300.00, committed 0.00, available 9700.00`.
Mutation m1 and m2: race tests **failed as expected**. Ruff lint and format checks are clean.
After the mutation runs, `git status` was clean, so the source was restored byte-for-byte.

**Not run:** no real AI client (Claude Desktop etc.) was connected; the demo script plays that role. Not tested on
Linux or macOS. No CI. No coverage report or load testing beyond the race tests.

## 4. AI-assisted approach

I used Claude Code throughout: requirements analysis, the spec, SDK investigation, and the code and tests, task by task
under the SPEC §8 loop. I reviewed each step and checked it against independent evidence. Fuller notes are in
[docs/AI_LOG.md](docs/AI_LOG.md).

1. **Requirements / spec.** Prompt (excerpt): *"explain … what is the problem and what solution we are gonna give … check we
   did not miss anything crucial."* The first summary missed several requirements; a second, line-by-line pass of the brief
   found them:
   - stored text must not grant permissions (→ R-04, AC-17);
   - participant and fund must belong to the caller's nonprofit (→ composite FKs, AC-14);
   - one identity per stdio process, so the demo needs one server per role;
   - the methodology must also cover reviewing AI-delegated work (→ SPEC §8).

   *Evidence:* each item traces to a sentence in the brief.
2. **Implementation planning.** The AI's prior knowledge was MCP SDK v1 (`FastMCP`), but `uv add mcp` resolved **2.3.0**.
   Reading the installed source showed that `FastMCP` had been renamed `MCPServer`, so the plan changed. A 30-line probe then
   showed that the SDK **silently ignores unknown arguments** (`{"role": "admin"}` → success), which became R-04 and AC-16.
   *Evidence:* SDK source and probe output, before any code was written.
3. **Verification and debugging.** To prove the race tests can fail, the AI wrote a mutation tool (a naive approval). It
   showed the tests fail, and that without the DB CHECK the fund really overspends. Corrections along the way:
   - the harness swallowed thread exceptions (it showed `not-run`), so it now reports the cause;
   - the first tool restored files with CRLF line endings, caught by `git status`;
   - a raw JSON-RPC test closed stdin too early, so the reply never arrived. The `outcome=ok` line in stderr showed the
     server was fine and the test was wrong.

## 5. Spec revisions

v1.0 was committed before any code. v1.1 changes (with reasons, SPEC §12):
- concurrent-retry criteria added to AC-10;
- unknown-tool-name behavior clarified;
- AC-23 made concrete as a raw JSON-RPC check;
- `python -m` commands, because of the Windows Application Control block.

No business rule changed during implementation.

## 6. Time spent

_To be filled in by the author._

## 7. Known limitations and next priorities

- **Limitations:**
  - Identity is a trusted environment variable: fine for a local stdio fixture, not for production (see SPEC §10 for OAuth).
  - SQLite has a single writer. That is correct but limits throughput; Postgres with the same guarded `UPDATE` would scale.
  - `list_requests` has a limit but no pagination cursor.
  - No audit-event table; who acted and when is stored on each request and payment row.
  - Approved-but-unpaid money stays committed forever, because cancellations are out of scope (SPEC A-7).
- **Next priorities:**
  1. Streamable HTTP + OAuth resource-server validation and membership mapping (SPEC §10).
  2. An append-only audit log.
  3. Ask the business the SPEC §11 questions, especially approval thresholds, fund purpose restrictions and releasing
     stale approvals.
  4. CI (Linux + Windows) running tests, lint and the mutation check.
  5. Pagination.
