"""Setup/reset command (R-23): `uv run funding-reset`. Separate from server start.

Drops and recreates all tables and loads the synthetic seed data from SPEC §9 in one transaction.
"""

import argparse
import logging
import sys
from pathlib import Path

from . import db
from .logging_setup import configure_logging

log = logging.getLogger("funding_mcp.seed")

NONPROFITS = [
    ("np_community_bridge", "Community Bridge"),
    ("np_harbor_aid", "Harbor Aid Collective"),
]

STAFF = [
    ("stf_cb_case_worker", "np_community_bridge", "Casey Rivera", "case_worker"),
    ("stf_cb_program_manager", "np_community_bridge", "Morgan Lee", "program_manager"),
    ("stf_cb_finance", "np_community_bridge", "Finley Shah", "finance"),
    ("stf_ha_case_worker", "np_harbor_aid", "Jordan Park", "case_worker"),
    ("stf_ha_program_manager", "np_harbor_aid", "Riley Adams", "program_manager"),
    ("stf_ha_finance", "np_harbor_aid", "Sam Patel", "finance"),
]

PARTICIPANTS = [
    ("par_cb_001", "np_community_bridge", "Alex Johnson"),
    ("par_cb_002", "np_community_bridge", "Bianca Torres"),
    ("par_cb_003", "np_community_bridge", "Chen Wei"),
    ("par_ha_001", "np_harbor_aid", "Dana Okafor"),
    ("par_ha_002", "np_harbor_aid", "Eli Novak"),
]

FUNDS = [  # allocation in cents
    ("fnd_cb_rent", "np_community_bridge", "Emergency Rent Relief Grant", 1_000_000),
    ("fnd_cb_utilities", "np_community_bridge", "Utility Assistance Grant", 250_000),
    ("fnd_cb_transit", "np_community_bridge", "Transit Access Grant", 50_000),
    ("fnd_ha_general", "np_harbor_aid", "General Hardship Fund", 800_000),
]


def reset_database(path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")  # readers don't block the single writer
        conn.execute("PRAGMA foreign_keys = OFF")  # allow dropping in any order
        with db.write_transaction(conn):
            for table in db.TABLES_IN_DROP_ORDER:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            for statement in db.SCHEMA.split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.executemany("INSERT INTO nonprofits (id, name) VALUES (?, ?)", NONPROFITS)
            conn.executemany("INSERT INTO staff (id, nonprofit_id, display_name, role) VALUES (?, ?, ?, ?)", STAFF)
            conn.executemany("INSERT INTO participants (id, nonprofit_id, full_name) VALUES (?, ?, ?)", PARTICIPANTS)
            conn.executemany("INSERT INTO funds (id, nonprofit_id, name, allocation_cents) VALUES (?, ?, ?, ?)", FUNDS)
            conn.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION}")
        conn.execute("PRAGMA foreign_keys = ON")
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Recreate the funding database with synthetic seed data.")
    parser.add_argument("--db", type=Path, default=None, help="database path (default: $FUNDING_DB_PATH)")
    args = parser.parse_args(argv)
    path = args.db or db.db_path_from_env()
    reset_database(path)
    log.info(
        "Database reset at %s: %d nonprofits, %d staff, %d participants, %d funds",
        path,
        len(NONPROFITS),
        len(STAFF),
        len(PARTICIPANTS),
        len(FUNDS),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
