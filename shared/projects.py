"""Project constants shared by server and client (stdlib only)."""

from __future__ import annotations

import enum


class ProjectCategory(str, enum.Enum):
    FIXED = "fixed"
    HOURLY = "hourly"
    MILESTONE = "milestone"


CATEGORY_LABELS = {
    ProjectCategory.FIXED: "Fixed",
    ProjectCategory.HOURLY: "Hourly",
    ProjectCategory.MILESTONE: "Milestone",
}

CURRENCY = "USD"
# Amounts travel and are stored as whole cents, so no float rounding ever touches money.
MAX_AMOUNT_CENTS = 10**13 - 1  # just under $100 billion

TITLE_MAX_LENGTH = 200
DETAILS_MAX_LENGTH = 20_000
PAYMENT_DESCRIPTION_MAX_LENGTH = 300
MAX_PAYMENTS = 500
FUND_LOCATION_MAX_LENGTH = 200
MAX_CODEVELOPERS = 50
CODEVELOPER_NATIONALITY_MAX_LENGTH = 100
CODEVELOPER_NAME_MAX_LENGTH = 200
CODEVELOPER_ID_MAX_LENGTH = 100
