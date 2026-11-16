"""T8: end-to-end through MCP over stdio. Each test launches the real server as a subprocess with a
fixture identity in its environment, exactly as an MCP client would (R-01, R-21, R-24, AC-15/16/21/23/24)."""

import json
import subprocess
import sys

import pytest
from conftest import CB_ALEX, CB_CASE, CB_FIN, CB_PM, CB_RENT, HA_PM, snapshot
from mcp import Client, StdioServerParameters

from funding_mcp import db

pytestmark = [pytest.mark.e2e, pytest.mark.anyio]

EXPECTED_TOOLS = {
    "get_current_staff",
    "list_participants",
    "list_funds",
    "create_assistance_request",
    "approve_request",
    "reject_request",
    "record_payment",
    "get_request",
    "list_requests",
    "get_funding_summary",
}
READ_ONLY = {
    "get_current_staff",
    "list_participants",
    "list_funds",
    "get_request",
    "list_requests",
    "get_funding_summary",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


def server(db_path, staff_id: str | None) -> StdioServerParameters:
    env = {"FUNDING_DB_PATH": str(db_path)}
    if staff_id is not None:
        env["FUNDING_STAFF_ID"] = staff_id
    return StdioServerParameters(command=sys.executable, args=["-m", "funding_mcp.server"], env=env)


async def call(db_path, staff_id, tool, args=None):
    async with Client(server(db_path, staff_id)) as client:
        return await client.call_tool(tool, args or {})


def error_code(result) -> str:
    assert result.is_error, result
    assert json.loads(result.content[0].text) == result.structured_content  # text mirrors structured envelope
    return result.structured_content["error"]["code"]


async def test_tool_discovery(db_path):
    """R-21, AC-21 (discovery), AC-24 (no edit tool)."""
    async with Client(server(db_path, CB_CASE)) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == EXPECTED_TOOLS
    for name, tool in tools.items():
        assert tool.description and len(tool.description) > 20, name
        assert tool.input_schema["type"] == "object", name
        assert tool.output_schema and tool.output_schema["type"] == "object", name
        assert bool(tool.annotations and tool.annotations.read_only_hint) == (name in READ_ONLY), name
    create = tools["create_assistance_request"].input_schema
    assert set(create["required"]) == {"participant_id", "fund_id", "purpose", "amount"}
    assert create["properties"]["amount"]["type"] == "string" and "pattern" in create["properties"]["amount"]
    assert not {"staff_id", "role", "nonprofit_id"} & set(create["properties"])
    assert not any(word in name for name in tools for word in ("update", "edit", "delete"))


async def test_business_case_workflow_over_mcp(db_path):
    """AC-21: case worker creates -> manager approves -> finance pays -> summary, each its own server process."""
    created = await call(
        db_path,
        CB_CASE,
        "create_assistance_request",
        {"participant_id": CB_ALEX, "fund_id": CB_RENT, "purpose": "rent", "amount": "300.00"},
    )
    assert not created.is_error, created
    request_id = created.structured_content["request"]["request_id"]
    assert created.structured_content["request"]["status"] == "pending"

    approved = await call(db_path, CB_PM, "approve_request", {"request_id": request_id})
    assert approved.structured_content["fund"]["available"] == {"cents": 970000, "usd": "9700.00"}

    paid = await call(db_path, CB_FIN, "record_payment", {"request_id": request_id, "payment_reference": "SIM-1"})
    assert paid.structured_content["request"]["status"] == "paid"

    summary = await call(db_path, CB_FIN, "get_funding_summary", {"fund_id": CB_RENT})
    rent = summary.structured_content["funds"][0]
    assert (rent["paid"]["usd"], rent["committed"]["usd"], rent["available"]["usd"]) == ("300.00", "0.00", "9700.00")

    retry = await call(db_path, CB_FIN, "record_payment", {"request_id": request_id})
    assert retry.structured_content["replayed"] is True  # R-14 over MCP


@pytest.mark.parametrize("staff_id", [None, "", "stf_does_not_exist"])
async def test_missing_or_unknown_identity_over_mcp(db_path, staff_id):
    """AC-15: server starts, but every call is refused."""
    result = await call(db_path, staff_id, "list_funds")
    assert error_code(result) == "UNAUTHENTICATED"


async def test_unknown_arguments_are_rejected(db_path):
    """AC-16: arguments cannot smuggle identity or role; the SDK alone would silently ignore them."""
    conn = db.open_existing(db_path)
    before = snapshot(conn)
    for extra in ({"role": "program_manager"}, {"nonprofit_id": "np_harbor_aid"}, {"staff_id": CB_PM}):
        args = {"participant_id": CB_ALEX, "fund_id": CB_RENT, "purpose": "rent", "amount": "10.00"} | extra
        result = await call(db_path, CB_CASE, "create_assistance_request", args)
        assert error_code(result) == "VALIDATION_ERROR"
        assert result.structured_content["error"]["details"]["fields"] == list(extra)
    assert snapshot(conn) == before
    conn.close()


@pytest.mark.parametrize(
    ("args", "fields"),
    [
        ({"amount": 300}, ["amount"]),  # JSON number, not a decimal string
        ({"amount": "300.001"}, ["amount"]),
        ({"purpose": "holiday"}, ["purpose"]),
        ({"amount": None}, ["amount"]),
    ],
)
async def test_schema_violations_return_structured_validation_errors(db_path, args, fields):
    """AC-18 over MCP: rejected before reaching business code, with a stable error code."""
    base = {"participant_id": CB_ALEX, "fund_id": CB_RENT, "purpose": "rent", "amount": "300.00"}
    result = await call(db_path, CB_CASE, "create_assistance_request", base | args)
    assert error_code(result) == "VALIDATION_ERROR"
    assert result.structured_content["error"]["details"]["fields"] == fields


async def test_role_and_tenant_errors_over_mcp(db_path):
    """AC-11, AC-12 over MCP."""
    created = await call(
        db_path,
        CB_CASE,
        "create_assistance_request",
        {"participant_id": CB_ALEX, "fund_id": CB_RENT, "purpose": "rent", "amount": "50.00"},
    )
    request_id = created.structured_content["request"]["request_id"]
    assert error_code(await call(db_path, CB_CASE, "approve_request", {"request_id": request_id})) == "FORBIDDEN"
    assert error_code(await call(db_path, HA_PM, "approve_request", {"request_id": request_id})) == "NOT_FOUND"
    assert error_code(await call(db_path, HA_PM, "get_request", {"request_id": request_id})) == "NOT_FOUND"


def test_stdout_carries_only_protocol_and_logs_go_to_stderr(db_path):
    """AC-23 / R-24: drive the server with raw JSON-RPC; every stdout line must be a JSON-RPC message."""
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_funds", "arguments": {}}},
    ]
    proc = subprocess.Popen(
        [sys.executable, "-m", "funding_mcp.server"],
        env={"FUNDING_DB_PATH": str(db_path), "FUNDING_STAFF_ID": CB_FIN, "SYSTEMROOT": "C:\\Windows", "PATH": ""},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    proc.stdin.write("".join(json.dumps(m) + "\n" for m in messages))
    proc.stdin.flush()
    parsed = []
    while not any(m.get("id") == 2 for m in parsed):  # keep stdin open until the tool reply arrives
        line = proc.stdout.readline()
        assert line, "server closed stdout before answering"
        parsed.append(json.loads(line))  # raises if anything non-JSON reached stdout
    proc.stdin.close()  # EOF -> clean shutdown
    rest_out, stderr = proc.communicate(timeout=60)
    parsed += [json.loads(line) for line in rest_out.splitlines() if line.strip()]
    assert all(m.get("jsonrpc") == "2.0" for m in parsed)
    responses = {m["id"]: m for m in parsed if "id" in m}
    assert responses[2]["result"]["structuredContent"]["funds"][0]["fund_id"] == "fnd_cb_rent"
    assert "tool=list_funds staff=stf_cb_finance outcome=ok" in stderr


def test_server_refuses_to_start_without_initialized_db(tmp_path):
    """R-23: normal startup never creates or seeds the database."""
    missing = tmp_path / "nope.db"
    proc = subprocess.run(
        [sys.executable, "-m", "funding_mcp.server"],
        input="",
        env={"FUNDING_DB_PATH": str(missing), "FUNDING_STAFF_ID": CB_FIN, "SYSTEMROOT": "C:\\Windows", "PATH": ""},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "funding-reset" in proc.stderr
    assert not missing.exists()
