"""T5: create (R-07), idempotent submission (R-09), validation (§3.3), retrieval (R-18), summary (R-19)."""

import pytest
from conftest import CB_ALEX, CB_BIANCA, CB_CASE, CB_FIN, CB_PM, CB_RENT, CB_TRANSIT, CB_UTIL, snapshot
from test_access import new_request, who

from funding_mcp import service
from funding_mcp.errors import IdempotencyConflict, InvalidInput


def create(conn, **overrides):
    args = {"participant_id": CB_ALEX, "fund_id": CB_RENT, "purpose": "rent", "amount": "300.00"} | overrides
    return service.create_request(conn, who(conn, CB_CASE), **args)


def test_create_is_pending_and_reserves_nothing(conn):
    """AC-01"""
    result = create(conn, description="  March rent arrears  ")
    req = result["request"]
    assert req["status"] == "pending"
    assert req["amount"] == {"cents": 30000, "usd": "300.00"}
    assert (req["participant_id"], req["participant_name"]) == (CB_ALEX, "Alex Johnson")
    assert (req["fund_id"], req["fund_name"]) == (CB_RENT, "Emergency Rent Relief Grant")
    assert req["description"] == "March rent arrears"  # trimmed
    assert req["created_by"] == CB_CASE and req["created_at"].endswith("Z")
    assert req["decided_by"] is req["decided_at"] is req["decision_reason"] is req["payment"] is None
    assert req["request_id"].startswith("req_")
    assert result["replayed"] is False
    fund = result["fund"]
    assert fund["committed"]["cents"] == 0 and fund["available"]["usd"] == "10000.00"
    assert fund["pending"]["usd"] == "300.00"  # informational only


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"amount": "0"}, "amount"),
        ({"amount": "-1.00"}, "amount"),
        ({"amount": "1.001"}, "amount"),
        ({"amount": "abc"}, "amount"),
        ({"amount": "1000000.01"}, "amount"),
        ({"amount": 300}, "amount"),
        ({"purpose": "vacation"}, "purpose"),
        ({"purpose": "other"}, "description"),  # description required for "other"
        ({"purpose": "other", "description": "   "}, "description"),
        ({"description": "x" * 501}, "description"),
        ({"participant_id": ""}, "participant_id"),
        ({"fund_id": "f" * 101}, "fund_id"),
        ({"idempotency_key": "has space"}, "idempotency_key"),
        ({"idempotency_key": "k" * 101}, "idempotency_key"),
    ],
)
def test_invalid_create_inputs_change_nothing(conn, overrides, field):
    """AC-18, §3.3"""
    before = snapshot(conn)
    with pytest.raises(InvalidInput) as exc:
        create(conn, **overrides)
    assert exc.value.details["fields"] == [field]
    assert snapshot(conn) == before


def test_other_purpose_with_description_is_accepted(conn):
    req = create(conn, purpose="other", description="Replacement work boots")["request"]
    assert (req["purpose"], req["description"]) == ("other", "Replacement work boots")


def test_idempotent_create(conn):
    """AC-20"""
    first = create(conn, idempotency_key="intake-42")
    second = create(conn, idempotency_key="intake-42")
    assert second["replayed"] is True
    assert second["request"] == first["request"]
    with pytest.raises(IdempotencyConflict):
        create(conn, idempotency_key="intake-42", amount="301.00")
    assert len(service.list_requests(conn, who(conn, CB_CASE))["requests"]) == 1
    # without a key, an identical submission is a new request (SPEC A-11)
    create(conn)
    assert len(service.list_requests(conn, who(conn, CB_CASE))["requests"]) == 2


def test_get_and_list_requests_with_filters(conn):
    """R-18"""
    a = new_request(conn, amount="100.00")
    b = new_request(conn, participant=CB_BIANCA, fund=CB_UTIL, amount="50.00")
    c = new_request(conn, fund=CB_TRANSIT, amount="20.00")
    pm, fin = who(conn, CB_PM), who(conn, CB_FIN)
    service.approve_request(conn, pm, a)
    service.reject_request(conn, pm, b, reason="Duplicate of an earlier request")

    def ids(**filters):
        return [r["request_id"] for r in service.list_requests(conn, fin, **filters)["requests"]]

    assert ids() == [c, b, a]  # newest first
    assert ids(status="approved") == [a]
    assert ids(status="rejected") == [b]
    assert ids(fund_id=CB_TRANSIT) == [c]
    assert ids(participant_id=CB_BIANCA) == [b]
    assert ids(participant_id=CB_ALEX, status="pending") == [c]
    assert ids(limit=1) == [c]
    got = service.get_request(conn, fin, b)["request"]
    assert (got["status"], got["decided_by"], got["decision_reason"]) == (
        "rejected",
        CB_PM,
        "Duplicate of an earlier request",
    )


@pytest.mark.parametrize(
    ("filters", "field"), [({"status": "done"}, "status"), ({"limit": 0}, "limit"), ({"limit": 101}, "limit")]
)
def test_list_requests_validates_filters(conn, filters, field):
    with pytest.raises(InvalidInput) as exc:
        service.list_requests(conn, who(conn, CB_PM), **filters)
    assert exc.value.details["fields"] == [field]


def test_participant_name_filter(conn):
    """R-05"""
    found = service.list_participants(conn, who(conn, CB_CASE), name_contains="BIAN")["participants"]
    assert found == [{"participant_id": CB_BIANCA, "full_name": "Bianca Torres"}]


def test_funding_summary_totals(conn):
    """R-19"""
    a = new_request(conn, amount="300.00")
    new_request(conn, fund=CB_TRANSIT, amount="25.50")
    service.approve_request(conn, who(conn, CB_PM), a)
    summary = service.get_funding_summary(conn, who(conn, CB_FIN))
    rent = next(f for f in summary["funds"] if f["fund_id"] == CB_RENT)
    assert rent["request_counts"] == {"pending": 0, "approved": 1, "rejected": 0, "paid": 0}
    totals = summary["totals"]
    assert totals["allocation"]["usd"] == "13000.00"
    assert totals["committed"]["usd"] == "300.00"
    assert totals["pending"]["usd"] == "25.50"
    assert totals["available"]["usd"] == "12700.00"
    one = service.get_funding_summary(conn, who(conn, CB_FIN), fund_id=CB_TRANSIT)
    assert [f["fund_id"] for f in one["funds"]] == [CB_TRANSIT]
    assert one["totals"]["pending"]["cents"] == 2550
