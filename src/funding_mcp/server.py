"""MCP server (stdio). Thin adapter: schemas + error envelope here, all business rules in `service`.

Start:  FUNDING_STAFF_ID=stf_cb_case_worker uv run funding-mcp
Per call (SPEC §3.4): resolve identity -> reject unknown arguments -> SDK schema validation -> service.
"""

import inspect
import json
import logging
import os
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, Field, ValidationError

from . import db, schemas, service
from .errors import DomainError, InvalidInput
from .logging_setup import configure_logging
from .money import AMOUNT_PATTERN

log = logging.getLogger("funding_mcp.server")

READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
CREATE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
TRANSITION = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

INSTRUCTIONS = (
    "Emergency assistance funding for one nonprofit. Your identity and role are fixed by the server "
    "configuration; arguments cannot change them. Money is USD: send amounts as decimal strings like "
    '"300.00"; responses give {cents, usd}. Workflow: case worker creates (pending, no money reserved) -> '
    "program manager approves (reserves amount) or rejects -> finance records payment (committed -> paid)."
)

# Reusable input field types (SPEC §3.3). Business code re-validates; these make the schema self-describing.
RecordId = Annotated[str, Field(min_length=1, max_length=100)]
RequestId = Annotated[str, Field(min_length=1, max_length=100, description="ID returned by create_assistance_request")]
Text500 = Annotated[str, Field(min_length=1, max_length=500)]


def _result(payload: BaseModel | dict[str, Any], is_error: bool = False) -> CallToolResult:
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(data))], structured_content=data, is_error=is_error
    )


class FundingServer(MCPServer):
    def __init__(self, db_path: Path, staff_id: str | None):
        super().__init__(name="emergency-assistance-funding", version="0.1.0", instructions=INSTRUCTIONS)
        self.db_path = db_path
        self.staff_id = staff_id
        self._parameters: dict[str, frozenset[str]] = {}
        self._register_tools()

    # ---- request pipeline ------------------------------------------------------------------------

    async def call_tool(self, name: str, arguments: dict[str, Any], context: Any = None) -> Any:
        try:
            self._check_identity()  # 1. identity first, before anything about the call is evaluated
            unknown = set(arguments) - self._parameters.get(name, frozenset(arguments))
            if unknown:  # 2. the SDK would silently drop these (see docs/AI_LOG.md #3); refuse instead
                raise InvalidInput("Unknown argument(s) for this tool.", sorted(unknown))
            result = await super().call_tool(name, arguments, context)  # 3. schema validation + tool
        except DomainError as exc:
            result = _result(exc.to_envelope(), is_error=True)
        except ToolError as exc:
            if not isinstance(exc.__cause__, ValidationError):
                raise  # e.g. unknown tool name: the SDK reports it
            fields = sorted({str(err["loc"][0]) for err in exc.__cause__.errors() if err["loc"]})
            result = _result(
                InvalidInput("Arguments do not match the tool's input schema.", fields).to_envelope(), True
            )
        outcome = result.structured_content["error"]["code"] if result.is_error else "ok"
        log.info("tool=%s staff=%s outcome=%s", name, self.staff_id, outcome)
        return result

    def _check_identity(self) -> None:
        conn = db.open_existing(self.db_path)
        try:
            service.resolve_caller(conn, self.staff_id)
        finally:
            conn.close()

    def _run(self, operation: Callable[..., dict[str, Any]], output: type[BaseModel], **kwargs: Any) -> CallToolResult:
        """Open a per-call connection, resolve the caller from trusted config, run the service operation."""
        conn: sqlite3.Connection | None = None
        try:
            conn = db.open_existing(self.db_path)
            caller = service.resolve_caller(conn, self.staff_id)
            return _result(output.model_validate(operation(conn, caller, **kwargs)))
        except DomainError as exc:
            return _result(exc.to_envelope(), is_error=True)
        except Exception:
            log.exception("unexpected error in %s", operation.__name__)
            envelope = {"error": {"code": "INTERNAL_ERROR", "message": "Unexpected server error.", "details": {}}}
            return _result(envelope, is_error=True)
        finally:
            if conn is not None:
                conn.close()

    def _tool(self, fn: Callable[..., Any], annotations: ToolAnnotations) -> None:
        self._parameters[fn.__name__] = frozenset(inspect.signature(fn).parameters)
        description = " ".join((inspect.getdoc(fn) or "").split())  # one line for clients
        self.add_tool(fn, name=fn.__name__, description=description, annotations=annotations)

    # ---- tools (SPEC §5.2) -----------------------------------------------------------------------

    def _register_tools(self) -> None:
        run = self._run

        def get_current_staff() -> Annotated[CallToolResult, schemas.Staff]:
            """Who am I? Returns the staff identity this server acts as: name, role and nonprofit. Any role."""
            return run(service.get_current_staff, schemas.Staff)

        def list_participants(
            name_contains: Annotated[
                str | None, Field(max_length=100, description="Case-insensitive name filter")
            ] = None,
        ) -> Annotated[CallToolResult, schemas.ParticipantList]:
            """List participants of your nonprofit, optionally filtered by name. Any role. Read-only."""
            return run(service.list_participants, schemas.ParticipantList, name_contains=name_contains)

        def list_funds() -> Annotated[CallToolResult, schemas.FundList]:
            """List your nonprofit's grant funds with their fixed allocations. Any role. Read-only."""
            return run(service.list_funds, schemas.FundList)

        def create_assistance_request(
            participant_id: Annotated[RecordId, Field(description="Existing participant of your nonprofit")],
            fund_id: Annotated[RecordId, Field(description="Fund of your nonprofit to pay from")],
            purpose: Annotated[
                Literal["rent", "utilities", "transportation", "other"], Field(description="Expense category")
            ],
            amount: Annotated[
                str, Field(pattern=AMOUNT_PATTERN, description='USD decimal string > 0, max 2 decimals, e.g. "300.00"')
            ],
            description: Annotated[Text500 | None, Field(description="Details; required when purpose is other")] = None,
            idempotency_key: Annotated[
                str | None,
                Field(
                    pattern=r"^[A-Za-z0-9_.:-]{1,100}$",
                    description="Optional; resending the same key returns the original request instead of a duplicate",
                ),
            ] = None,
        ) -> Annotated[CallToolResult, schemas.MutationResult]:
            """Submit an assistance request (case workers only).
            It starts pending and reserves NO money; a program manager must approve it."""
            return run(
                service.create_request,
                schemas.MutationResult,
                participant_id=participant_id,
                fund_id=fund_id,
                purpose=purpose,
                amount=amount,
                description=description,
                idempotency_key=idempotency_key,
            )

        def approve_request(request_id: RequestId) -> Annotated[CallToolResult, schemas.MutationResult]:
            """Approve a pending request (program managers only).
            Atomically reserves the full amount from its fund; fails with INSUFFICIENT_FUNDS if the
            fund's available balance is too low. Repeating it is safe."""
            return run(service.approve_request, schemas.MutationResult, request_id=request_id)

        def reject_request(
            request_id: RequestId,
            reason: Annotated[Text500 | None, Field(description="Why it was rejected")] = None,
        ) -> Annotated[CallToolResult, schemas.MutationResult]:
            """Reject a pending request (program managers only). Funding is unchanged. Repeating it is safe."""
            return run(service.reject_request, schemas.MutationResult, request_id=request_id, reason=reason)

        def record_payment(
            request_id: RequestId,
            payment_reference: Annotated[
                str | None, Field(min_length=1, max_length=100, description="Simulated check/transfer reference")
            ] = None,
        ) -> Annotated[CallToolResult, schemas.MutationResult]:
            """Record the simulated payment of an approved request (finance only), for the full approved amount.
            Moves it from committed to paid; available is unchanged.
            Succeeds once; retries return the original payment."""
            return run(
                service.record_payment,
                schemas.MutationResult,
                request_id=request_id,
                payment_reference=payment_reference,
            )

        def get_request(request_id: RequestId) -> Annotated[CallToolResult, schemas.RequestResult]:
            """Get one assistance request with its status, decision and payment. Any role. Read-only."""
            return run(service.get_request, schemas.RequestResult, request_id=request_id)

        def list_requests(
            status: Annotated[
                Literal["pending", "approved", "rejected", "paid"] | None, Field(description="Filter by status")
            ] = None,
            fund_id: Annotated[RecordId | None, Field(description="Filter by fund")] = None,
            participant_id: Annotated[RecordId | None, Field(description="Filter by participant")] = None,
            limit: Annotated[int, Field(ge=1, le=100, description="Max results, newest first")] = 50,
        ) -> Annotated[CallToolResult, schemas.RequestList]:
            """List your nonprofit's assistance requests, newest first, with optional filters. Any role. Read-only."""
            return run(
                service.list_requests,
                schemas.RequestList,
                status=status,
                fund_id=fund_id,
                participant_id=participant_id,
                limit=limit,
            )

        def get_funding_summary(
            fund_id: Annotated[RecordId | None, Field(description="Only this fund; omit for all funds")] = None,
        ) -> Annotated[CallToolResult, schemas.FundingSummary]:
            """Funding summary per fund and totals: allocation, committed, paid,
            available (= allocation - committed - paid) and pending (not reserved). Any role. Read-only."""
            return run(service.get_funding_summary, schemas.FundingSummary, fund_id=fund_id)

        for fn in (get_current_staff, list_participants, list_funds, get_request, list_requests, get_funding_summary):
            self._tool(fn, READ)
        self._tool(create_assistance_request, CREATE)
        for fn in (approve_request, reject_request, record_payment):
            self._tool(fn, TRANSITION)


def main() -> int:
    configure_logging()
    db_path = db.db_path_from_env()
    staff_id = os.environ.get("FUNDING_STAFF_ID")
    try:
        conn = db.open_existing(db_path)
    except db.DatabaseNotInitialized as exc:
        log.error("%s", exc)
        return 2
    try:
        caller = service.resolve_caller(conn, staff_id)
        log.info("starting as %s (%s, %s); db=%s", caller.staff_id, caller.role.value, caller.nonprofit_id, db_path)
    except DomainError as exc:
        log.warning("starting WITHOUT a valid identity (%s); every tool call will be refused", exc.message)
    finally:
        conn.close()
    FundingServer(db_path, staff_id).run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
