"""T6: state machine (R-10), approval/rejection/payment money effects (R-11..R-13), retries (R-14),
balance invariants (R-16, AC-25)."""

import pytest
from conftest import CB_FIN, CB_PM, CB_RENT, CB_TRANSIT, assert_invariants, snapshot
from test_access import new_request, who

from funding_mcp import service
from funding_mcp.errors import InsufficientFunds, InvalidTransition


def balances(conn, fund_id):
    f = service.get_funding_summary(conn, who(conn, CB_FIN), fund_id=fund_id)["funds"][0]
    return f["committed"]["usd"], f["paid"]["usd"], f["available"]["usd"]


def approve(conn, request_id):
    return service.approve_request(conn, who(conn, CB_PM), request_id)


def reject(conn, request_id, reason=None):
    return service.reject_request(conn, who(conn, CB_PM), request_id, reason=reason)


def pay(conn, request_id, reference=None):
    return service.record_payment(conn, who(conn, CB_FIN), request_id, payment_reference=reference)


def test_business_case_example(conn):
    """AC-01..03: approve $300 against $10,000, then pay it."""
    request_id = new_request(conn, amount="300.00")
    assert balances(conn, CB_RENT) == ("0.00", "0.00", "10000.00")

    approved = approve(conn, request_id)
    assert approved["request"]["status"] == "approved"
    assert approved["request"]["decided_by"] == CB_PM
    assert (approved["fund"]["committed"]["usd"], approved["fund"]["available"]["usd"]) == ("300.00", "9700.00")
    assert balances(conn, CB_RENT) == ("300.00", "0.00", "9700.00")

    paid = pay(conn, request_id, reference="CHK-1001")
    assert paid["request"]["status"] == "paid"
    payment = paid["request"]["payment"]
    assert payment["amount"] == {"cents": 30000, "usd": "300.00"}
    assert (payment["payment_reference"], payment["recorded_by"]) == ("CHK-1001", CB_FIN)
    assert balances(conn, CB_RENT) == ("0.00", "300.00", "9700.00")
    assert_invariants(conn)


def test_reject_leaves_funding_unchanged(conn):
    """AC-04"""
    request_id = new_request(conn)
    funds_before = snapshot(conn)["funds"]
    result = reject(conn, request_id, reason="  Outside program guidelines ")
    assert result["request"]["status"] == "rejected"
    assert result["request"]["decision_reason"] == "Outside program guidelines"
    assert snapshot(conn)["funds"] == funds_before


def test_insufficient_funds(conn):
    """AC-05: 500.00 fund with 400.00 committed cannot approve 200.00."""
    approve(conn, new_request(conn, fund=CB_TRANSIT, amount="400.00"))
    big = new_request(conn, fund=CB_TRANSIT, amount="200.00")
    before = snapshot(conn)
    with pytest.raises(InsufficientFunds) as exc:
        approve(conn, big)
    assert exc.value.details == {"fund_id": CB_TRANSIT, "available_cents": 10000, "requested_cents": 20000}
    assert snapshot(conn) == before
    assert service.get_request(conn, who(conn, CB_PM), big)["request"]["status"] == "pending"


def test_paid_money_still_counts_against_available(conn):
    """available = allocation - committed - paid: paying must not free the money again."""
    first = new_request(conn, fund=CB_TRANSIT, amount="400.00")
    approve(conn, first)
    pay(conn, first)
    with pytest.raises(InsufficientFunds):
        approve(conn, new_request(conn, fund=CB_TRANSIT, amount="100.01"))
    approve(conn, new_request(conn, fund=CB_TRANSIT, amount="100.00"))
    assert balances(conn, CB_TRANSIT) == ("100.00", "400.00", "0.00")
    assert_invariants(conn)


def test_exact_remaining_amount_can_be_approved(conn):
    """AC-06"""
    approve(conn, new_request(conn, fund=CB_TRANSIT, amount="499.99"))
    approve(conn, new_request(conn, fund=CB_TRANSIT, amount="0.01"))
    assert balances(conn, CB_TRANSIT) == ("500.00", "0.00", "0.00")
    with pytest.raises(InsufficientFunds):
        approve(conn, new_request(conn, fund=CB_TRANSIT, amount="0.01"))


def test_cent_amounts_accumulate_exactly(conn):
    """AC-19"""
    approve(conn, new_request(conn, fund=CB_TRANSIT, amount="0.10"))
    approve(conn, new_request(conn, fund=CB_TRANSIT, amount="0.20"))
    assert balances(conn, CB_TRANSIT) == ("0.30", "0.00", "499.70")


def test_repeated_approval_is_a_replay(conn):
    """AC-07"""
    request_id = new_request(conn)
    first = approve(conn, request_id)
    before = snapshot(conn)
    again = approve(conn, request_id)
    assert again["replayed"] is True
    assert again["request"] == first["request"]
    assert snapshot(conn) == before
    assert balances(conn, CB_RENT) == ("300.00", "0.00", "9700.00")


def test_payment_retry_is_a_replay(conn):
    """AC-08"""
    request_id = new_request(conn)
    approve(conn, request_id)
    first = pay(conn, request_id, reference="CHK-1")
    before = snapshot(conn)
    again = pay(conn, request_id, reference="CHK-2-retry")
    assert again["replayed"] is True
    assert again["request"]["payment"] == first["request"]["payment"]  # original payment returned
    assert snapshot(conn) == before
    assert len(before["payments"]) == 1
    assert balances(conn, CB_RENT) == ("0.00", "300.00", "9700.00")


def test_repeated_rejection_is_a_replay(conn):
    request_id = new_request(conn)
    reject(conn, request_id, reason="first")
    again = reject(conn, request_id, reason="second")
    assert again["replayed"] is True
    assert again["request"]["decision_reason"] == "first"


@pytest.mark.parametrize(
    ("setup", "action", "status"),
    [
        ([], "pay", "pending"),
        (["reject"], "approve", "rejected"),
        (["reject"], "pay", "rejected"),
        (["approve"], "reject", "approved"),
        (["approve", "pay"], "approve", "paid"),
        (["approve", "pay"], "reject", "paid"),
    ],
)
def test_invalid_transitions_change_nothing(conn, setup, action, status):
    """AC-09"""
    actions = {"approve": approve, "reject": reject, "pay": pay}
    request_id = new_request(conn)
    for step in setup:
        actions[step](conn, request_id)
    before = snapshot(conn)
    with pytest.raises(InvalidTransition) as exc:
        actions[action](conn, request_id)
    assert exc.value.details["current_status"] == status
    assert snapshot(conn) == before
    assert_invariants(conn)


def test_many_operations_keep_invariants(conn):
    """AC-25 over a mixed workload."""
    ids = [new_request(conn, fund=CB_TRANSIT, amount=f"{n}.25") for n in range(10, 200, 15)]
    for i, request_id in enumerate(ids):
        try:
            approve(conn, request_id)
        except InsufficientFunds:
            reject(conn, request_id)
            continue
        if i % 2:
            pay(conn, request_id)
        assert_invariants(conn)
    fund = service.get_funding_summary(conn, who(conn, CB_FIN), fund_id=CB_TRANSIT)["funds"][0]
    assert fund["committed"]["cents"] + fund["paid"]["cents"] + fund["available"]["cents"] == 50000
    assert fund["paid"]["cents"] > 0 and fund["request_counts"]["rejected"] > 0  # workload hit both paths
