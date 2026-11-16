"""Business service: the single policy-enforcement point (SPEC §3, §6).

Every public operation takes a resolved `Caller`; the nonprofit scope comes only from the caller.
Writes run inside `db.write_transaction` (BEGIN IMMEDIATE), so any error rolls back (R-20).
Evaluation order (SPEC §3.4): identity (resolve_caller) -> argument validation -> role -> lookup -> rules.
"""

import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from . import db
from .errors import (
    Forbidden,
    IdempotencyConflict,
    InsufficientFunds,
    InvalidInput,
    InvalidTransition,
    NotFound,
    Unauthenticated,
)
from .money import format_cents, money, parse_amount

PURPOSES = ("rent", "utilities", "transportation", "other")
STATUSES = ("pending", "approved", "rejected", "paid")
MAX_ID = 100
MAX_TEXT = 500
MAX_REFERENCE = 100
IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")


# ---- identity and policy (R-01, R-02) -------------------------------------------------------------


class Role(StrEnum):
    CASE_WORKER = "case_worker"
    PROGRAM_MANAGER = "program_manager"
    FINANCE = "finance"


class Action(StrEnum):
    READ = "read"
    CREATE_REQUEST = "create_request"
    DECIDE_REQUEST = "decide_request"
    RECORD_PAYMENT = "record_payment"


PERMISSIONS: dict[Role, frozenset[Action]] = {
    Role.CASE_WORKER: frozenset({Action.READ, Action.CREATE_REQUEST}),
    Role.PROGRAM_MANAGER: frozenset({Action.READ, Action.DECIDE_REQUEST}),
    Role.FINANCE: frozenset({Action.READ, Action.RECORD_PAYMENT}),
}


@dataclass(frozen=True)
class Caller:
    staff_id: str
    display_name: str
    role: Role
    nonprofit_id: str
    nonprofit_name: str


def resolve_caller(conn: sqlite3.Connection, staff_id: str | None) -> Caller:
    """Map the trusted fixture identity to its role and nonprofit, from the database only."""
    if not staff_id or not staff_id.strip():
        raise Unauthenticated("No staff identity configured. Set FUNDING_STAFF_ID for this server.")
    row = conn.execute(
        "SELECT s.id, s.display_name, s.role, s.nonprofit_id, n.name AS nonprofit_name"
        " FROM staff s JOIN nonprofits n ON n.id = s.nonprofit_id WHERE s.id = ?",
        (staff_id,),
    ).fetchone()
    if row is None:
        raise Unauthenticated("Unknown staff identity.")
    return Caller(row["id"], row["display_name"], Role(row["role"]), row["nonprofit_id"], row["nonprofit_name"])


def authorize(caller: Caller, action: Action) -> None:
    if action not in PERMISSIONS[caller.role]:
        raise Forbidden(
            f"Role {caller.role.value} is not permitted to {action.value.replace('_', ' ')}.",
            {"role": caller.role.value, "action": action.value},
        )


# ---- input validation (SPEC §3.3) ----------------------------------------------------------------


def _require_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_ID:
        raise InvalidInput(f"{field} must be a non-empty string of at most {MAX_ID} characters.", [field])
    return value


def _optional_text(value: object, field: str, max_len: int) -> str | None:
    if value is None:
        return None
    text = value.strip() if isinstance(value, str) else None
    if not text or len(text) > max_len:
        raise InvalidInput(f"{field} must be 1-{max_len} characters when provided.", [field])
    return text


def _choice(value: object, field: str, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise InvalidInput(f"{field} must be one of: {', '.join(allowed)}.", [field])
    return value  # type: ignore[return-value]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ---- read models (SPEC §5.1) ---------------------------------------------------------------------

_REQUEST_SELECT = """
SELECT r.*, p.full_name AS participant_name, f.name AS fund_name,
       pay.id AS payment_id, pay.amount_cents AS payment_amount_cents, pay.payment_reference,
       pay.recorded_by AS payment_recorded_by, pay.recorded_at AS payment_recorded_at
FROM assistance_requests r
JOIN participants p ON p.id = r.participant_id
JOIN funds f ON f.id = r.fund_id
LEFT JOIN payments pay ON pay.request_id = r.id
"""


def _request_view(row: sqlite3.Row) -> dict[str, Any]:
    payment = None
    if row["payment_id"] is not None:
        payment = {
            "payment_id": row["payment_id"],
            "amount": money(row["payment_amount_cents"]),
            "payment_reference": row["payment_reference"],
            "recorded_by": row["payment_recorded_by"],
            "recorded_at": row["payment_recorded_at"],
        }
    return {
        "request_id": row["id"],
        "participant_id": row["participant_id"],
        "participant_name": row["participant_name"],
        "fund_id": row["fund_id"],
        "fund_name": row["fund_name"],
        "purpose": row["purpose"],
        "description": row["description"],
        "amount": money(row["amount_cents"]),
        "status": row["status"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "decided_by": row["decided_by"],
        "decided_at": row["decided_at"],
        "decision_reason": row["decision_reason"],
        "payment": payment,
    }


def _load_request(conn: sqlite3.Connection, caller: Caller, request_id: str) -> dict[str, Any]:
    """Scoped lookup: another nonprofit's request is indistinguishable from a missing one (R-03)."""
    row = conn.execute(_REQUEST_SELECT + " WHERE r.id = ? AND r.nonprofit_id = ?", (request_id, caller.nonprofit_id))
    found = row.fetchone()
    if found is None:
        raise NotFound(f"Request {request_id} not found.")
    return _request_view(found)


_FUND_SUMMARY_SELECT = """
SELECT f.id, f.name, f.allocation_cents, f.committed_cents, f.paid_cents,
       COALESCE(SUM(CASE WHEN r.status = 'pending' THEN r.amount_cents END), 0) AS pending_cents,
       COUNT(CASE WHEN r.status = 'pending' THEN 1 END)  AS n_pending,
       COUNT(CASE WHEN r.status = 'approved' THEN 1 END) AS n_approved,
       COUNT(CASE WHEN r.status = 'rejected' THEN 1 END) AS n_rejected,
       COUNT(CASE WHEN r.status = 'paid' THEN 1 END)     AS n_paid
FROM funds f
LEFT JOIN assistance_requests r ON r.fund_id = f.id
WHERE f.nonprofit_id = ? {extra}
GROUP BY f.id
ORDER BY f.name
"""


def _fund_summary_view(row: sqlite3.Row) -> dict[str, Any]:
    available = row["allocation_cents"] - row["committed_cents"] - row["paid_cents"]
    return {
        "fund_id": row["id"],
        "name": row["name"],
        "allocation": money(row["allocation_cents"]),
        "committed": money(row["committed_cents"]),
        "paid": money(row["paid_cents"]),
        "available": money(available),
        "pending": money(row["pending_cents"]),
        "request_counts": {
            "pending": row["n_pending"],
            "approved": row["n_approved"],
            "rejected": row["n_rejected"],
            "paid": row["n_paid"],
        },
    }


def _fund_summaries(conn: sqlite3.Connection, caller: Caller, fund_id: str | None = None) -> list[dict[str, Any]]:
    extra, params = ("AND f.id = ?", (caller.nonprofit_id, fund_id)) if fund_id else ("", (caller.nonprofit_id,))
    rows = conn.execute(_FUND_SUMMARY_SELECT.format(extra=extra), params).fetchall()
    if fund_id and not rows:
        raise NotFound(f"Fund {fund_id} not found.")
    return [_fund_summary_view(r) for r in rows]


def _mutation_result(conn: sqlite3.Connection, caller: Caller, request_id: str, replayed: bool) -> dict[str, Any]:
    request = _load_request(conn, caller, request_id)
    fund = _fund_summaries(conn, caller, request["fund_id"])[0]
    return {"request": request, "fund": fund, "replayed": replayed}


def _require_status(request: dict[str, Any], expected: str, action: str) -> None:
    if request["status"] != expected:
        raise InvalidTransition(
            f"Cannot {action} request {request['request_id']}: status is {request['status']}, expected {expected}.",
            {"current_status": request["status"], "action": action},
        )


# ---- read operations -----------------------------------------------------------------------------


def get_current_staff(conn: sqlite3.Connection, caller: Caller) -> dict[str, Any]:
    authorize(caller, Action.READ)
    return {
        "staff_id": caller.staff_id,
        "display_name": caller.display_name,
        "role": caller.role.value,
        "nonprofit_id": caller.nonprofit_id,
        "nonprofit_name": caller.nonprofit_name,
    }


def list_participants(conn: sqlite3.Connection, caller: Caller, name_contains: str | None = None) -> dict[str, Any]:
    name_contains = _optional_text(name_contains, "name_contains", MAX_ID)
    authorize(caller, Action.READ)
    sql = "SELECT id, full_name FROM participants WHERE nonprofit_id = ?"
    params: list[Any] = [caller.nonprofit_id]
    if name_contains:
        sql += " AND instr(lower(full_name), lower(?)) > 0"  # literal match; no LIKE wildcards
        params.append(name_contains)
    rows = conn.execute(sql + " ORDER BY full_name", params).fetchall()
    return {"participants": [{"participant_id": r["id"], "full_name": r["full_name"]} for r in rows]}


def list_funds(conn: sqlite3.Connection, caller: Caller) -> dict[str, Any]:
    authorize(caller, Action.READ)
    rows = conn.execute(
        "SELECT id, name, allocation_cents FROM funds WHERE nonprofit_id = ? ORDER BY name", (caller.nonprofit_id,)
    ).fetchall()
    return {
        "funds": [{"fund_id": r["id"], "name": r["name"], "allocation": money(r["allocation_cents"])} for r in rows]
    }


def get_request(conn: sqlite3.Connection, caller: Caller, request_id: str) -> dict[str, Any]:
    request_id = _require_id(request_id, "request_id")
    authorize(caller, Action.READ)
    return {"request": _load_request(conn, caller, request_id)}


def list_requests(
    conn: sqlite3.Connection,
    caller: Caller,
    status: str | None = None,
    fund_id: str | None = None,
    participant_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if status is not None:
        _choice(status, "status", STATUSES)
    if fund_id is not None:
        _require_id(fund_id, "fund_id")
    if participant_id is not None:
        _require_id(participant_id, "participant_id")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise InvalidInput("limit must be an integer from 1 to 100.", ["limit"])
    authorize(caller, Action.READ)
    sql = _REQUEST_SELECT + " WHERE r.nonprofit_id = ?"
    params: list[Any] = [caller.nonprofit_id]
    for column, value in (("r.status", status), ("r.fund_id", fund_id), ("r.participant_id", participant_id)):
        if value is not None:
            sql += f" AND {column} = ?"
            params.append(value)
    sql += " ORDER BY r.created_at DESC, r.rowid DESC LIMIT ?"
    params.append(limit)
    return {"requests": [_request_view(r) for r in conn.execute(sql, params).fetchall()]}


def get_funding_summary(conn: sqlite3.Connection, caller: Caller, fund_id: str | None = None) -> dict[str, Any]:
    if fund_id is not None:
        _require_id(fund_id, "fund_id")
    authorize(caller, Action.READ)
    funds = _fund_summaries(conn, caller, fund_id)
    totals = {
        key: money(sum(f[key]["cents"] for f in funds))
        for key in ("allocation", "committed", "paid", "available", "pending")
    }
    return {"funds": funds, "totals": totals}


# ---- write operations ----------------------------------------------------------------------------


def create_request(
    conn: sqlite3.Connection,
    caller: Caller,
    *,
    participant_id: str,
    fund_id: str,
    purpose: str,
    amount: str,
    description: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """R-07: new request is pending and reserves no money. R-09: optional idempotent replay."""
    participant_id = _require_id(participant_id, "participant_id")
    fund_id = _require_id(fund_id, "fund_id")
    purpose = _choice(purpose, "purpose", PURPOSES)
    amount_cents = parse_amount(amount)
    description = _optional_text(description, "description", MAX_TEXT)
    if purpose == "other" and description is None:
        raise InvalidInput("description is required when purpose is other.", ["description"])
    if idempotency_key is not None and (
        not isinstance(idempotency_key, str) or not IDEMPOTENCY_KEY_RE.fullmatch(idempotency_key)
    ):
        raise InvalidInput("idempotency_key must be 1-100 characters of A-Z a-z 0-9 _ . : -", ["idempotency_key"])
    authorize(caller, Action.CREATE_REQUEST)

    with db.write_transaction(conn):
        for table, record_id, label in (("participants", participant_id, "Participant"), ("funds", fund_id, "Fund")):
            exists = conn.execute(
                f"SELECT 1 FROM {table} WHERE id = ? AND nonprofit_id = ?", (record_id, caller.nonprofit_id)
            ).fetchone()
            if exists is None:
                raise NotFound(f"{label} {record_id} not found.")

        if idempotency_key is not None:
            prior = conn.execute(
                "SELECT id, participant_id, fund_id, purpose, description, amount_cents FROM assistance_requests"
                " WHERE nonprofit_id = ? AND created_by = ? AND idempotency_key = ?",
                (caller.nonprofit_id, caller.staff_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                same = (prior["participant_id"], prior["fund_id"], prior["purpose"], prior["description"]) == (
                    participant_id,
                    fund_id,
                    purpose,
                    description,
                ) and prior["amount_cents"] == amount_cents
                if not same:
                    raise IdempotencyConflict(
                        "idempotency_key was already used for a different request.",
                        {"request_id": prior["id"]},
                    )
                return _mutation_result(conn, caller, prior["id"], replayed=True)

        request_id = f"req_{uuid.uuid4().hex}"
        conn.execute(
            "INSERT INTO assistance_requests (id, nonprofit_id, participant_id, fund_id, purpose, description,"
            " amount_cents, status, created_by, created_at, idempotency_key)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
            (
                request_id,
                caller.nonprofit_id,
                participant_id,
                fund_id,
                purpose,
                description,
                amount_cents,
                caller.staff_id,
                _now(),
                idempotency_key,
            ),
        )
        return _mutation_result(conn, caller, request_id, replayed=False)


def approve_request(conn: sqlite3.Connection, caller: Caller, request_id: str) -> dict[str, Any]:
    """R-11/R-17: check and reserve in one serialized transaction with a guarded UPDATE."""
    request_id = _require_id(request_id, "request_id")
    authorize(caller, Action.DECIDE_REQUEST)
    with db.write_transaction(conn):
        request = _load_request(conn, caller, request_id)
        if request["status"] == "approved":
            return _mutation_result(conn, caller, request_id, replayed=True)  # R-14
        _require_status(request, "pending", "approve")
        amount_cents = request["amount"]["cents"]
        reserved = conn.execute(
            "UPDATE funds SET committed_cents = committed_cents + ?"
            " WHERE id = ? AND nonprofit_id = ? AND allocation_cents - committed_cents - paid_cents >= ?",
            (amount_cents, request["fund_id"], caller.nonprofit_id, amount_cents),
        ).rowcount
        if reserved != 1:
            fund = _fund_summaries(conn, caller, request["fund_id"])[0]
            available = fund["available"]["cents"]
            raise InsufficientFunds(
                f"Fund {request['fund_id']} has {format_cents(available)} available; "
                f"request needs {format_cents(amount_cents)}.",
                {"fund_id": request["fund_id"], "available_cents": available, "requested_cents": amount_cents},
            )
        _set_status(conn, request_id, "pending", "approved", caller, reason=None)
        return _mutation_result(conn, caller, request_id, replayed=False)


def reject_request(
    conn: sqlite3.Connection, caller: Caller, request_id: str, reason: str | None = None
) -> dict[str, Any]:
    """R-12: pending -> rejected, funding unchanged."""
    request_id = _require_id(request_id, "request_id")
    reason = _optional_text(reason, "reason", MAX_TEXT)
    authorize(caller, Action.DECIDE_REQUEST)
    with db.write_transaction(conn):
        request = _load_request(conn, caller, request_id)
        if request["status"] == "rejected":
            return _mutation_result(conn, caller, request_id, replayed=True)  # R-14
        _require_status(request, "pending", "reject")
        _set_status(conn, request_id, "pending", "rejected", caller, reason=reason)
        return _mutation_result(conn, caller, request_id, replayed=False)


def record_payment(
    conn: sqlite3.Connection, caller: Caller, request_id: str, payment_reference: str | None = None
) -> dict[str, Any]:
    """R-13: full approved amount, once; committed -> paid, available unchanged."""
    request_id = _require_id(request_id, "request_id")
    payment_reference = _optional_text(payment_reference, "payment_reference", MAX_REFERENCE)
    authorize(caller, Action.RECORD_PAYMENT)
    with db.write_transaction(conn):
        request = _load_request(conn, caller, request_id)
        if request["status"] == "paid":
            return _mutation_result(conn, caller, request_id, replayed=True)  # R-14
        _require_status(request, "approved", "pay")
        amount_cents = request["amount"]["cents"]
        conn.execute(
            "INSERT INTO payments (id, request_id, nonprofit_id, amount_cents, payment_reference, recorded_by,"
            " recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                f"pay_{uuid.uuid4().hex}",
                request_id,
                caller.nonprofit_id,
                amount_cents,
                payment_reference,
                caller.staff_id,
                _now(),
            ),
        )
        moved = conn.execute(
            "UPDATE funds SET committed_cents = committed_cents - ?, paid_cents = paid_cents + ?"
            " WHERE id = ? AND nonprofit_id = ? AND committed_cents >= ?",
            (amount_cents, amount_cents, request["fund_id"], caller.nonprofit_id, amount_cents),
        ).rowcount
        if moved != 1:  # would mean counters drifted from requests; refuse rather than corrupt
            raise RuntimeError(f"fund {request['fund_id']} committed balance is inconsistent")
        conn.execute(
            "UPDATE assistance_requests SET status = 'paid' WHERE id = ? AND status = 'approved'", (request_id,)
        )
        return _mutation_result(conn, caller, request_id, replayed=False)


def _set_status(
    conn: sqlite3.Connection, request_id: str, current: str, new: str, caller: Caller, reason: str | None
) -> None:
    changed = conn.execute(
        "UPDATE assistance_requests SET status = ?, decided_by = ?, decided_at = ?, decision_reason = ?"
        " WHERE id = ? AND status = ?",
        (new, caller.staff_id, _now(), reason, request_id, current),
    ).rowcount
    if changed != 1:
        raise RuntimeError(f"request {request_id} changed status concurrently")
