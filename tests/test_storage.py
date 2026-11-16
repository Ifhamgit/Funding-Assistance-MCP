"""T3: schema, seed/reset (R-22, R-23, AC-22) and database-level guards (R-03, R-13, R-16)."""

import sqlite3
import subprocess
import sys

import pytest
from conftest import CB_ALEX, CB_CASE, CB_RENT, HA_GENERAL, snapshot

from funding_mcp import db
from funding_mcp.seed import reset_database


def _count(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


def test_seed_matches_spec(conn):
    assert _count(conn, "SELECT COUNT(*) FROM nonprofits") == 2
    for np_id, participants, funds in (("np_community_bridge", 3, 3), ("np_harbor_aid", 2, 1)):
        roles = {r[0] for r in conn.execute("SELECT role FROM staff WHERE nonprofit_id = ?", (np_id,)).fetchall()}
        assert roles == {"case_worker", "program_manager", "finance"}
        assert _count(conn, "SELECT COUNT(*) FROM participants WHERE nonprofit_id = ?", np_id) == participants
        assert _count(conn, "SELECT COUNT(*) FROM funds WHERE nonprofit_id = ?", np_id) == funds
    rent = conn.execute("SELECT * FROM funds WHERE id = ?", (CB_RENT,)).fetchone()
    assert (rent["allocation_cents"], rent["committed_cents"], rent["paid_cents"]) == (1_000_000, 0, 0)
    assert _count(conn, "SELECT COUNT(*) FROM assistance_requests") == 0


def test_reset_is_repeatable(db_path):
    """AC-22: reset after arbitrary changes returns the exact seed state."""
    conn = db.open_existing(db_path)
    fresh = snapshot(conn)
    conn.execute("UPDATE funds SET committed_cents = 500 WHERE id = ?", (CB_RENT,))
    conn.execute(
        "INSERT INTO assistance_requests (id, nonprofit_id, participant_id, fund_id, purpose, amount_cents,"
        " status, created_by, created_at) VALUES ('req_x', 'np_community_bridge', ?, ?, 'rent', 500,"
        " 'approved', ?, '2026-01-01T00:00:00Z')",
        (CB_ALEX, CB_RENT, CB_CASE),
    )
    conn.close()

    reset_database(db_path)
    conn = db.open_existing(db_path)
    assert snapshot(conn) == fresh
    conn.close()

    reset_database(db_path)  # twice in a row is fine too
    conn = db.open_existing(db_path)
    assert snapshot(conn) == fresh
    conn.close()


def test_open_existing_rejects_missing_or_uninitialized(tmp_path):
    with pytest.raises(db.DatabaseNotInitialized):
        db.open_existing(tmp_path / "missing.db")
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    with pytest.raises(db.DatabaseNotInitialized):
        db.open_existing(empty)


def test_db_rejects_overspend_counters(conn):
    """R-16 enforced by CHECK constraint, independent of application code."""
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE funds SET committed_cents = 1000001 WHERE id = ?", (CB_RENT,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE funds SET committed_cents = 600000, paid_cents = 400001 WHERE id = ?", (CB_RENT,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE funds SET paid_cents = -1 WHERE id = ?", (CB_RENT,))


def test_db_rejects_cross_nonprofit_request(conn):
    """R-03: a Community Bridge request cannot reference a Harbor Aid fund (composite FK)."""
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO assistance_requests (id, nonprofit_id, participant_id, fund_id, purpose, amount_cents,"
            " status, created_by, created_at) VALUES ('req_x', 'np_community_bridge', ?, ?, 'rent', 100,"
            " 'pending', ?, '2026-01-01T00:00:00Z')",
            (CB_ALEX, HA_GENERAL, CB_CASE),
        )


def test_db_allows_one_payment_per_request(conn):
    """R-13: UNIQUE(request_id) on payments."""
    conn.execute(
        "INSERT INTO assistance_requests (id, nonprofit_id, participant_id, fund_id, purpose, amount_cents,"
        " status, created_by, created_at) VALUES ('req_x', 'np_community_bridge', ?, ?, 'rent', 100,"
        " 'paid', ?, '2026-01-01T00:00:00Z')",
        (CB_ALEX, CB_RENT, CB_CASE),
    )
    insert = (
        "INSERT INTO payments (id, request_id, nonprofit_id, amount_cents, recorded_by, recorded_at)"
        " VALUES (?, 'req_x', 'np_community_bridge', 100, 'stf_cb_finance', '2026-01-01T00:00:00Z')"
    )
    conn.execute(insert, ("pay_1",))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("pay_2",))


@pytest.mark.parametrize(
    ("column", "value"), [("amount_cents", 0), ("amount_cents", -5), ("status", "cancelled"), ("purpose", "x")]
)
def test_db_rejects_invalid_request_values(conn, column, value):
    values = {"amount_cents": 100, "status": "pending", "purpose": "rent"} | {column: value}
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO assistance_requests (id, nonprofit_id, participant_id, fund_id, purpose, amount_cents,"
            " status, created_by, created_at) VALUES ('req_x', 'np_community_bridge', ?, ?, ?, ?, ?, ?,"
            " '2026-01-01T00:00:00Z')",
            (CB_ALEX, CB_RENT, values["purpose"], values["amount_cents"], values["status"], CB_CASE),
        )


def test_reset_cli_uses_env_path(tmp_path):
    """R-23: `funding-reset` is a standalone command driven by FUNDING_DB_PATH."""
    target = tmp_path / "cli.db"
    result = subprocess.run(
        [sys.executable, "-m", "funding_mcp.seed"],
        env={"FUNDING_DB_PATH": str(target), "SYSTEMROOT": "C:\\Windows", "PATH": ""},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""  # reporting goes to stderr
    conn = db.open_existing(target)
    assert _count(conn, "SELECT COUNT(*) FROM nonprofits") == 2
    conn.close()
