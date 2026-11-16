import os
import sqlite3

import pytest

from funding_mcp import db
from funding_mcp.seed import reset_database


def subprocess_env(**env: str) -> dict[str, str]:
    """Environment for server/CLI subprocesses. Forwards coverage's subprocess hook when measuring coverage
    (the MCP stdio client passes only a fixed whitelist of variables). No effect on behavior."""
    if "COVERAGE_PROCESS_CONFIG" in os.environ:
        env["COVERAGE_PROCESS_CONFIG"] = os.environ["COVERAGE_PROCESS_CONFIG"]
    return env


# Seed IDs (SPEC §9)
CB_CASE = "stf_cb_case_worker"
CB_PM = "stf_cb_program_manager"
CB_FIN = "stf_cb_finance"
HA_CASE = "stf_ha_case_worker"
HA_PM = "stf_ha_program_manager"
HA_FIN = "stf_ha_finance"
CB_RENT = "fnd_cb_rent"  # 10,000.00
CB_UTIL = "fnd_cb_utilities"  # 2,500.00
CB_TRANSIT = "fnd_cb_transit"  # 500.00
HA_GENERAL = "fnd_ha_general"  # 8,000.00
CB_ALEX = "par_cb_001"
CB_BIANCA = "par_cb_002"
HA_DANA = "par_ha_001"


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "funding.db"
    reset_database(path)
    return path


@pytest.fixture
def conn(db_path):
    connection = db.open_existing(db_path)
    yield connection
    connection.close()


def snapshot(conn: sqlite3.Connection) -> dict[str, list[tuple]]:
    """Full business state, used to prove 'unchanged' (SPEC §7 definition)."""
    return {
        table: [tuple(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()]
        for table in ("funds", "assistance_requests", "payments")
    }


def assert_invariants(conn: sqlite3.Connection) -> None:
    """AC-25: stored counters equal derived sums; R-16 invariants hold."""
    rows = conn.execute(
        """
        SELECT f.id, f.allocation_cents, f.committed_cents, f.paid_cents,
               COALESCE((SELECT SUM(amount_cents) FROM assistance_requests r
                         WHERE r.fund_id = f.id AND r.status = 'approved'), 0) AS derived_committed,
               COALESCE((SELECT SUM(p.amount_cents) FROM payments p
                         JOIN assistance_requests r ON r.id = p.request_id
                         WHERE r.fund_id = f.id), 0) AS derived_paid,
               COALESCE((SELECT SUM(amount_cents) FROM assistance_requests r
                         WHERE r.fund_id = f.id AND r.status = 'paid'), 0) AS paid_status_sum
        FROM funds f
        """
    ).fetchall()
    for r in rows:
        assert r["committed_cents"] == r["derived_committed"], dict(r)
        assert r["paid_cents"] == r["derived_paid"] == r["paid_status_sum"], dict(r)
        assert r["committed_cents"] >= 0 and r["paid_cents"] >= 0
        assert r["committed_cents"] + r["paid_cents"] <= r["allocation_cents"], dict(r)
