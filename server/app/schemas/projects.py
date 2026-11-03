from __future__ import annotations

from datetime import date, datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.projects import (
    DETAILS_MAX_LENGTH,
    MAX_AMOUNT_CENTS,
    MAX_PAYMENTS,
    PAYMENT_DESCRIPTION_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    ProjectCategory,
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


class PaymentIn(BaseModel):
    """A payment history entry. With `id` it updates that entry; without, it adds one."""

    id: int | None = None
    paid_on: date
    description: str = Field(default="", max_length=PAYMENT_DESCRIPTION_MAX_LENGTH)
    amount_cents: int = Field(gt=0, le=MAX_AMOUNT_CENTS)

    @field_validator("description")
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
        return self


class PaymentOut(BaseModel):
    id: int
    paid_on: date
    description: str
    amount_cents: int


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
    paid_cents: int
    details: str
    team_id: int | None
    team_name: str | None
    created_by_id: int | None
    created_by_name: str | None
    leader_check: CheckOut | None
    owner_check: CheckOut | None
    payments: list[PaymentOut]
    created_at: datetime
    updated_at: datetime
    access: ProjectAccess
