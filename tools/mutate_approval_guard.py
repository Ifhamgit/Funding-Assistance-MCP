"""Mutation check for R-17: prove the race tests FAIL against a naive approval, then restore the code.

    uv run python tools/mutate_approval_guard.py m1   # naive check-then-write, DB CHECK constraint kept
    uv run python tools/mutate_approval_guard.py m2   # ... and the DB CHECK constraint removed too

The original files are restored in a `finally` block, even if the run is interrupted.
Expected: race tests fail (m1 with an IntegrityError from the CHECK constraint; m2 with real overspend).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "funding_mcp" / "service.py"
DB = ROOT / "src" / "funding_mcp" / "db.py"
RACE_TESTS = [
    "tests/test_concurrency.py::test_two_competing_approvals_cannot_overspend",
    "tests/test_concurrency.py::test_many_way_race_approves_exactly_what_fits",
]

GUARD = "WHERE id = ? AND nonprofit_id = ? AND allocation_cents - committed_cents - paid_cents >= ?"
NAIVE_CHECK = (
    '        _fund = _fund_summaries(conn, caller, request["fund_id"])[0]\n'
    "        import time; time.sleep(0.05)  # widen the window between check and write\n"
    '        if _fund["available"]["cents"] < amount_cents:\n'
    '            raise InsufficientFunds("naive", {})\n'
)
DB_CHECK = (
    ",\n    -- R-16: the database itself refuses any overspend, whatever the application does.\n"
    "    CHECK (committed_cents >= 0 AND paid_cents >= 0\n"
    "           AND committed_cents + paid_cents <= allocation_cents)"
)


def mutate(mode: str) -> None:
    service = SERVICE.read_text()
    assert GUARD in service, "guarded UPDATE not found"
    service = service.replace(GUARD, "WHERE id = ? AND nonprofit_id = ? AND ? IS NOT NULL")
    anchor = "        reserved = conn.execute(\n"
    service = service.replace(anchor, NAIVE_CHECK + anchor, 1)
    SERVICE.write_text(service)

    db = DB.read_text()
    for statement in ('conn.execute("BEGIN IMMEDIATE")', 'conn.execute("ROLLBACK")', 'conn.execute("COMMIT")'):
        assert statement in db
        db = db.replace(statement, "pass  # mutation: no transaction")
    if mode == "m2":
        assert DB_CHECK in db, "CHECK constraint not found"
        db = db.replace(DB_CHECK, "")
    DB.write_text(db)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "m1"
    if mode not in ("m1", "m2"):
        print(__doc__)
        return 2
    originals = {SERVICE: SERVICE.read_bytes(), DB: DB.read_bytes()}  # exact bytes
    try:
        mutate(mode)
        result = subprocess.run([sys.executable, "-m", "pytest", *RACE_TESTS, "-q", "--no-header"], cwd=ROOT)
    finally:
        for path, text in originals.items():
            path.write_bytes(text)
    print(f"\nmutation {mode}: race tests {'FAILED as expected' if result.returncode else 'PASSED (BAD!)'}")
    return 0 if result.returncode else 1


if __name__ == "__main__":
    sys.exit(main())
