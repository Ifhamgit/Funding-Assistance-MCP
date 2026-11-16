"""Tool output schemas (SPEC §5.1). Published to clients as each tool's outputSchema."""

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["pending", "approved", "rejected", "paid"]
Purpose = Literal["rent", "utilities", "transportation", "other"]
RoleName = Literal["case_worker", "program_manager", "finance"]


class Money(BaseModel):
    cents: int = Field(ge=0, description="Exact amount in integer US cents")
    usd: str = Field(description='Same amount as a decimal string, e.g. "300.00"')


class Staff(BaseModel):
    staff_id: str
    display_name: str
    role: RoleName
    nonprofit_id: str
    nonprofit_name: str


class Participant(BaseModel):
    participant_id: str
    full_name: str


class ParticipantList(BaseModel):
    participants: list[Participant]


class Fund(BaseModel):
    fund_id: str
    name: str
    allocation: Money


class FundList(BaseModel):
    funds: list[Fund]


class RequestCounts(BaseModel):
    pending: int
    approved: int
    rejected: int
    paid: int


class FundSummary(BaseModel):
    fund_id: str
    name: str
    allocation: Money
    committed: Money = Field(description="Reserved by approved, unpaid requests")
    paid: Money = Field(description="Recorded payments")
    available: Money = Field(description="allocation - committed - paid")
    pending: Money = Field(description="Sum of pending requests; informational, NOT reserved")
    request_counts: RequestCounts


class Totals(BaseModel):
    allocation: Money
    committed: Money
    paid: Money
    available: Money
    pending: Money


class FundingSummary(BaseModel):
    funds: list[FundSummary]
    totals: Totals


class Payment(BaseModel):
    payment_id: str
    amount: Money
    payment_reference: str | None
    recorded_by: str
    recorded_at: str


class AssistanceRequest(BaseModel):
    request_id: str
    participant_id: str
    participant_name: str
    fund_id: str
    fund_name: str
    purpose: Purpose
    description: str | None
    amount: Money
    status: Status
    created_by: str
    created_at: str
    decided_by: str | None
    decided_at: str | None
    decision_reason: str | None
    payment: Payment | None


class RequestResult(BaseModel):
    request: AssistanceRequest


class RequestList(BaseModel):
    requests: list[AssistanceRequest]


class MutationResult(BaseModel):
    request: AssistanceRequest
    fund: FundSummary = Field(description="The request's fund after this call")
    replayed: bool = Field(description="True if this call repeated an already-applied action and changed nothing")
