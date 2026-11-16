"""T7: competing approvals cannot overspend (R-17, AC-10), concurrent retries have one effect (R-14).

Each competitor uses its own SQLite connection (threads) or its own OS process, like separate MCP
server processes sharing the database. A barrier releases them at the same moment.
"""

import multiprocessing
import threading
from pathlib import Path

import pytest
from conftest import CB_ALEX, CB_CASE, CB_FIN, CB_PM, CB_TRANSIT, assert_invariants

from funding_mcp import db, service
from funding_mcp.errors import DomainError
from funding_mcp.seed import reset_database

ROUNDS = 25


def _create(path: Path, amount: str, count: int) -> list[str]:
    conn = db.open_existing(path)
    me = service.resolve_caller(conn, CB_CASE)
    ids = [
        service.create_request(
            conn, me, participant_id=CB_ALEX, fund_id=CB_TRANSIT, purpose="transportation", amount=amount
        )["request"]["request_id"]
        for _ in range(count)
    ]
    conn.close()
    return ids


def _attempt(path: str, staff: str, operation: str, request_id: str, barrier) -> tuple[str, bool | None]:
    """Run one operation on a fresh connection after all competitors are ready. Returns (outcome, replayed)."""
    conn = db.open_existing(path)
    try:
        caller = service.resolve_caller(conn, staff)
        barrier.wait(timeout=30)
        fn = service.approve_request if operation == "approve" else service.record_payment
        result = fn(conn, caller, request_id)
        return "ok", result["replayed"]
    except DomainError as exc:
        return exc.code, None
    except Exception as exc:  # surfaced in the assertion message instead of dying silently in a thread
        return f"UNEXPECTED {type(exc).__name__}: {exc}", None
    finally:
        conn.close()


def _race_threads(path: Path, staff: str, operation: str, request_ids: list[str]) -> list[tuple[str, bool | None]]:
    barrier = threading.Barrier(len(request_ids))
    results: list[tuple[str, bool | None]] = [("not-run", None)] * len(request_ids)

    def run(i: int, request_id: str) -> None:
        results[i] = _attempt(str(path), staff, operation, request_id, barrier)

    threads = [threading.Thread(target=run, args=(i, rid)) for i, rid in enumerate(request_ids)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


def _summary(path: Path) -> dict:
    conn = db.open_existing(path)
    try:
        assert_invariants(conn)
        return service.get_funding_summary(conn, service.resolve_caller(conn, CB_FIN), fund_id=CB_TRANSIT)["funds"][0]
    finally:
        conn.close()


@pytest.mark.slow
def test_two_competing_approvals_cannot_overspend(tmp_path):
    """AC-10: two 300.00 approvals race for a 500.00 fund, repeated ROUNDS times on fresh databases."""
    for round_no in range(ROUNDS):
        path = tmp_path / f"race{round_no}.db"
        reset_database(path)
        results = _race_threads(path, CB_PM, "approve", _create(path, "300.00", 2))
        outcomes = sorted(code for code, _ in results)
        assert outcomes == ["INSUFFICIENT_FUNDS", "ok"], f"round {round_no}: {results}"
        fund = _summary(path)
        assert (fund["committed"]["usd"], fund["available"]["usd"]) == ("300.00", "200.00")


@pytest.mark.slow
def test_many_way_race_approves_exactly_what_fits(db_path):
    """AC-10 N-way: 20 x 50.00 on a 500.00 fund -> exactly 10 approved."""
    results = _race_threads(db_path, CB_PM, "approve", _create(db_path, "50.00", 20))
    codes = [code for code, _ in results]
    assert codes.count("ok") == 10 and codes.count("INSUFFICIENT_FUNDS") == 10, results
    fund = _summary(db_path)
    assert (fund["committed"]["cents"], fund["available"]["cents"]) == (50000, 0)


@pytest.mark.slow
def test_same_request_approved_concurrently_reserves_once(db_path):
    """R-14 under concurrency: 8 simultaneous approvals of one request -> 1 effect, 7 replays."""
    [request_id] = _create(db_path, "120.00", 1)
    results = _race_threads(db_path, CB_PM, "approve", [request_id] * 8)
    assert sorted(results) == [("ok", False)] + [("ok", True)] * 7, results
    assert _summary(db_path)["committed"]["usd"] == "120.00"


@pytest.mark.slow
def test_concurrent_payment_retries_pay_once(db_path):
    """AC-08 under concurrency: 8 simultaneous payments of one request -> one payment row."""
    [request_id] = _create(db_path, "75.25", 1)
    conn = db.open_existing(db_path)
    service.approve_request(conn, service.resolve_caller(conn, CB_PM), request_id)
    conn.close()
    results = _race_threads(db_path, CB_FIN, "pay", [request_id] * 8)
    assert sorted(results) == [("ok", False)] + [("ok", True)] * 7, results
    fund = _summary(db_path)
    assert (fund["committed"]["usd"], fund["paid"]["usd"], fund["available"]["usd"]) == ("0.00", "75.25", "424.75")


@pytest.mark.slow
def test_competing_approvals_across_processes(db_path):
    """AC-10 across OS processes (separate server processes share the DB file): 6 x 300.00 on 500.00."""
    request_ids = _create(db_path, "300.00", 6)
    ctx = multiprocessing.get_context("spawn")
    with ctx.Manager() as manager:
        barrier = manager.Barrier(len(request_ids))
        with ctx.Pool(len(request_ids)) as pool:
            results = pool.starmap(
                _attempt, [(str(db_path), CB_PM, "approve", rid, barrier) for rid in request_ids], chunksize=1
            )
    codes = [code for code, _ in results]
    assert codes.count("ok") == 1 and codes.count("INSUFFICIENT_FUNDS") == 5, results
    assert _summary(db_path)["committed"]["usd"] == "300.00"
