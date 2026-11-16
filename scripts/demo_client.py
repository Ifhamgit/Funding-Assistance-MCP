"""Reproducible MCP client demonstration (no language model involved).

    uv run python scripts/demo_client.py

Resets a separate demo database (data/demo.db), then talks to the real server over stdio, launching it
once per fixture identity, as an MCP client configured for that staff member would:

  1. discover tools                     (case worker)
  2. create a $300 rent request         (case worker)
  3. approve it                         (program manager)
  4. record the simulated payment       (finance)
  5. read the final funding summary     (finance)
  + two guard-rail checks: a case worker trying to approve, and a payment retry.

Exits non-zero if any result differs from the business-case example.
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

from funding_mcp.seed import reset_database

ROOT = Path(__file__).resolve().parents[1]
DEMO_DB = ROOT / "data" / "demo.db"
CASE_WORKER, PROGRAM_MANAGER, FINANCE = "stf_cb_case_worker", "stf_cb_program_manager", "stf_cb_finance"


def server_as(staff_id: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "funding_mcp.server"],
        env={"FUNDING_STAFF_ID": staff_id, "FUNDING_DB_PATH": str(DEMO_DB), "FUNDING_LOG_LEVEL": "WARNING"},
        cwd=str(ROOT),
    )


async def call(staff_id: str, tool: str, args: dict | None = None) -> dict:
    async with Client(server_as(staff_id)) as client:
        result = await client.call_tool(tool, args or {})
    data = result.structured_content
    label = "ERROR" if result.is_error else "ok"
    print(f"  [{staff_id} -> {tool}] {label}")
    return data


def show(title: str, value: object) -> None:
    print(f"    {title}: {json.dumps(value)}")


def expect(condition: bool, message: str) -> None:
    if not condition:
        print(f"\nDEMO FAILED: {message}")
        sys.exit(1)


async def main() -> None:
    reset_database(DEMO_DB)
    print(f"Reset demo database {DEMO_DB}\n")

    print("1. Discover tools")
    async with Client(server_as(CASE_WORKER)) as client:
        tools = (await client.list_tools()).tools
    for tool in tools:
        print(f"    - {tool.name}: {tool.description[:90]}")
    expect(len(tools) == 10, "expected 10 tools")

    me = await call(CASE_WORKER, "get_current_staff")
    show("caller", {k: me[k] for k in ("display_name", "role", "nonprofit_name")})
    funds = await call(CASE_WORKER, "list_funds")
    show("funds", [(f["fund_id"], f["allocation"]["usd"]) for f in funds["funds"]])

    print("\n2. Case worker creates a $300.00 rent request")
    created = await call(
        CASE_WORKER,
        "create_assistance_request",
        {
            "participant_id": "par_cb_001",
            "fund_id": "fnd_cb_rent",
            "purpose": "rent",
            "amount": "300.00",
            "description": "November rent shortfall",
        },
    )
    request_id = created["request"]["request_id"]
    show("request", {"id": request_id, "status": created["request"]["status"]})
    show("fund available (nothing reserved yet)", created["fund"]["available"]["usd"])
    expect(created["request"]["status"] == "pending", "new request should be pending")

    print("\n   Guard rail: the case worker tries to approve their own request")
    denied = await call(CASE_WORKER, "approve_request", {"request_id": request_id})
    show("error", denied["error"]["code"])
    expect(denied["error"]["code"] == "FORBIDDEN", "case worker must not approve")

    print("\n3. Program manager approves")
    approved = await call(PROGRAM_MANAGER, "approve_request", {"request_id": request_id})
    fund = approved["fund"]
    show("committed / available", [fund["committed"]["usd"], fund["available"]["usd"]])
    expect(fund["available"]["usd"] == "9700.00", "approval should leave 9700.00 available")

    print("\n4. Finance records the simulated payment")
    paid = await call(FINANCE, "record_payment", {"request_id": request_id, "payment_reference": "SIM-0001"})
    show("payment", {k: paid["request"]["payment"][k] for k in ("payment_id", "payment_reference")})

    print("\n   Guard rail: finance retries the same payment")
    retry = await call(FINANCE, "record_payment", {"request_id": request_id})
    show("replayed", retry["replayed"])
    expect(retry["replayed"] is True, "retry must not pay twice")

    print("\n5. Final funding summary")
    summary = await call(FINANCE, "get_funding_summary", {"fund_id": "fnd_cb_rent"})
    rent = summary["funds"][0]
    final = {k: rent[k]["usd"] for k in ("allocation", "committed", "paid", "available")}
    show("Emergency Rent Relief Grant", final)
    expect(
        final == {"allocation": "10000.00", "committed": "0.00", "paid": "300.00", "available": "9700.00"},
        "final summary should be 300.00 paid, 0.00 committed, 9700.00 available",
    )
    print("\nDEMO PASSED: matches the business-case example (300.00 paid, 0.00 committed, 9700.00 available).")


if __name__ == "__main__":
    asyncio.run(main())
