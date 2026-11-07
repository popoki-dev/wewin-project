from __future__ import annotations

from datetime import date, datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.projects import (
    CODEVELOPER_CONTACT_MAX_LENGTH,
    CODEVELOPER_ID_MAX_LENGTH,
    CODEVELOPER_NAME_MAX_LENGTH,
    CODEVELOPER_NATIONALITY_MAX_LENGTH,
    DETAILS_MAX_LENGTH,
    FUND_LOCATION_MAX_LENGTH,
    MAX_AMOUNT_CENTS,
    MAX_CODEVELOPERS,
    MAX_PAYMENTS,
    PAYMENT_DESCRIPTION_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    ProjectCategory,
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


class CodeveloperIn(BaseModel):
    """A co-developer. With `id` it updates that entry; without, it adds one."""

    id: int | None = None
    nationality: str = Field(default="", max_length=CODEVELOPER_NATIONALITY_MAX_LENGTH)
    name: str = Field(default="", max_length=CODEVELOPER_NAME_MAX_LENGTH)
    external_id: str = Field(default="", max_length=CODEVELOPER_ID_MAX_LENGTH)
    contact: str = Field(default="", max_length=CODEVELOPER_CONTACT_MAX_LENGTH)

    @field_validator("nationality", "name", "external_id", "contact")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _something(self) -> CodeveloperIn:
        if not (self.nationality or self.name or self.external_id):
            raise ValueError("Each co-developer needs a nationality, a name or an ID.")
        return self


class PayoutIn(BaseModel):
    """What a payment paid one co-developer, who is given by position in the project's
    `codevelopers` list (so a new co-developer can be paid in the same request)."""

    codeveloper_index: int = Field(ge=0)
    amount_cents: int = Field(gt=0, le=MAX_AMOUNT_CENTS)


class PaymentIn(BaseModel):
    """A payment history entry. With `id` it updates that entry; without, it adds one."""

    id: int | None = None
    paid_on: date
    description: str = Field(default="", max_length=PAYMENT_DESCRIPTION_MAX_LENGTH)
    amount_cents: int = Field(gt=0, le=MAX_AMOUNT_CENTS)  # total received
    my_share_cents: int = Field(default=0, ge=0, le=MAX_AMOUNT_CENTS)  # the portion you received
    fund_location: str = Field(default="", max_length=FUND_LOCATION_MAX_LENGTH)
    payouts: list[PayoutIn] = Field(default_factory=list, max_length=MAX_CODEVELOPERS)

    @field_validator("description", "fund_location")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class ProjectIn(BaseModel):
    """A whole project: create sends it, update replaces it (including the payment list)."""

    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    start_date: date = Field(default_factory=_today)
    end_date: date | None = None
    category: ProjectCategory
    # Required for fixed and milestone projects; hourly projects may leave it out.
    total_budget_cents: int | None = Field(default=None, ge=0, le=MAX_AMOUNT_CENTS)
    monthly_budget_cents: int | None = Field(default=None, ge=0, le=MAX_AMOUNT_CENTS)
    # Kept exactly as entered (no trimming), so line breaks and spacing survive.
    details: str = Field(default="", max_length=DETAILS_MAX_LENGTH)
    team_id: int | None = None
    codevelopers: list[CodeveloperIn] = Field(default_factory=list, max_length=MAX_CODEVELOPERS)
    payments: list[PaymentIn] = Field(default_factory=list, max_length=MAX_PAYMENTS)

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Enter a project title.")
        return v

    @model_validator(mode="after")
    def _check(self) -> ProjectIn:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("The completion date cannot be before the start date.")
        if self.total_budget_cents is None and self.category != ProjectCategory.HOURLY:
            raise ValueError("Enter the total budget (only hourly projects may leave it blank).")
        for n, payment in enumerate(self.payments, start=1):
            indexes = [p.codeveloper_index for p in payment.payouts]
            if any(i >= len(self.codevelopers) for i in indexes):
                raise ValueError(f"Payment {n}: a payout is to a co-developer who is not on the project.")
            if len(indexes) != len(set(indexes)):
                raise ValueError(f"Payment {n}: each co-developer can be paid only once per payment.")
            if payment.my_share_cents + sum(p.amount_cents for p in payment.payouts) > payment.amount_cents:
                raise ValueError(f"Payment {n}: your portion and the payouts are more than the total received.")
        return self


class CodeveloperOut(BaseModel):
    id: int
    nationality: str
    name: str
    external_id: str
    contact: str


class PayoutOut(BaseModel):
    codeveloper_id: int
    codeveloper_label: str  # name, else ID, else nationality
    amount_cents: int


class PaymentOut(BaseModel):
    id: int
    paid_on: date
    description: str
    amount_cents: int  # total received
    my_share_cents: int
    fund_location: str
    payouts: list[PayoutOut]
    paid_out_cents: int
    remaining_cents: int


class CheckOut(BaseModel):
    at: datetime
    by: str | None  # None if that account was deleted


class ProjectAccess(BaseModel):
    """What the caller may do with this project now."""

    edit: bool
    delete: bool
    check: bool  # place their check (Leader or Owner)
    uncheck: bool  # remove a check they may remove


class ProjectOut(BaseModel):
    id: int
    title: str
    start_date: date
    end_date: date | None
    category: str
    total_budget_cents: int | None
    monthly_budget_cents: int | None
    paid_cents: int  # total received over all payments
    remaining_cents: int  # what is left of it after portions and payouts
    details: str
    team_id: int | None
    team_name: str | None
    created_by_id: int | None
    created_by_name: str | None
    leader_check: CheckOut | None
    owner_check: CheckOut | None
    codevelopers: list[CodeveloperOut]
    payments: list[PaymentOut]
    created_at: datetime
    updated_at: datetime
    access: ProjectAccess
