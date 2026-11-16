"""SQLite storage (R-22): schema, connections and transactions. See SPEC §4."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "funding.db"
BUSY_TIMEOUT_MS = 10_000

SCHEMA = """
CREATE TABLE nonprofits (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE staff (
    id           TEXT PRIMARY KEY,
    nonprofit_id TEXT NOT NULL REFERENCES nonprofits(id),
    display_name TEXT NOT NULL,
    role         TEXT NOT NULL CHECK (role IN ('case_worker', 'program_manager', 'finance'))
);

CREATE TABLE participants (
    id           TEXT PRIMARY KEY,
    nonprofit_id TEXT NOT NULL REFERENCES nonprofits(id),
    full_name    TEXT NOT NULL,
    UNIQUE (id, nonprofit_id)
);

CREATE TABLE funds (
    id               TEXT PRIMARY KEY,
    nonprofit_id     TEXT NOT NULL REFERENCES nonprofits(id),
    name             TEXT NOT NULL,
    allocation_cents INTEGER NOT NULL CHECK (allocation_cents > 0),
    committed_cents  INTEGER NOT NULL DEFAULT 0,
    paid_cents       INTEGER NOT NULL DEFAULT 0,
    UNIQUE (id, nonprofit_id),
    -- R-16: the database itself refuses any overspend, whatever the application does.
    CHECK (committed_cents >= 0 AND paid_cents >= 0
           AND committed_cents + paid_cents <= allocation_cents)
);

CREATE TABLE assistance_requests (
    id              TEXT PRIMARY KEY,
    nonprofit_id    TEXT NOT NULL REFERENCES nonprofits(id),
    participant_id  TEXT NOT NULL,
    fund_id         TEXT NOT NULL,
    purpose         TEXT NOT NULL CHECK (purpose IN ('rent', 'utilities', 'transportation', 'other')),
    description     TEXT,
    amount_cents    INTEGER NOT NULL CHECK (amount_cents > 0),
    status          TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'paid')),
    created_by      TEXT NOT NULL REFERENCES staff(id),
    created_at      TEXT NOT NULL,
    idempotency_key TEXT,
    decided_by      TEXT REFERENCES staff(id),
    decided_at      TEXT,
    decision_reason TEXT,
    -- R-03: participant and fund must belong to the request's nonprofit.
    FOREIGN KEY (participant_id, nonprofit_id) REFERENCES participants(id, nonprofit_id),
    FOREIGN KEY (fund_id, nonprofit_id) REFERENCES funds(id, nonprofit_id),
    UNIQUE (nonprofit_id, created_by, idempotency_key)
);
CREATE INDEX ix_requests_scope ON assistance_requests (nonprofit_id, status, created_at);

CREATE TABLE payments (
    id                TEXT PRIMARY KEY,
    request_id        TEXT NOT NULL UNIQUE REFERENCES assistance_requests(id),  -- R-13: one payment
    nonprofit_id      TEXT NOT NULL REFERENCES nonprofits(id),
    amount_cents      INTEGER NOT NULL CHECK (amount_cents > 0),
    payment_reference TEXT,
    recorded_by       TEXT NOT NULL REFERENCES staff(id),
    recorded_at       TEXT NOT NULL
);
"""

TABLES_IN_DROP_ORDER = ("payments", "assistance_requests", "funds", "participants", "staff", "nonprofits")


class DatabaseNotInitialized(RuntimeError):
    pass


def db_path_from_env() -> Path:
    value = os.environ.get("FUNDING_DB_PATH", "").strip()
    return Path(value) if value else DEFAULT_DB_PATH


def connect(path: Path | str) -> sqlite3.Connection:
    # isolation_level=None: we issue BEGIN/COMMIT ourselves so transaction boundaries are explicit.
    # check_same_thread=False: the MCP SDK may run a call on a worker thread; each call still
    # uses its own short-lived connection, never shared between concurrent calls.
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return conn


def open_existing(path: Path | str) -> sqlite3.Connection:
    """Open a database created by `funding-reset`; never creates or migrates (R-23)."""
    path = Path(path)
    if not path.is_file():
        raise DatabaseNotInitialized(f"Database {path} not found. Run `uv run funding-reset` first.")
    conn = connect(path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        conn.close()
        raise DatabaseNotInitialized(
            f"Database {path} has schema version {version}, expected {SCHEMA_VERSION}. "
            "Run `uv run funding-reset` first."
        )
    return conn


@contextmanager
def write_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE takes SQLite's write lock up front, so check-then-update sequences inside
    are serialized against every other writer (R-17). Any exception rolls everything back (R-20)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
