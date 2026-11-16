from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from .base import AwareDateTime, Base, utcnow
from .team import Team
from .user import User


class Reviewable:
    """An item that a Team Leader and then the Owner review (expected revenue rows,
    co-developers, payments). A Leader review locks it for the user who entered it, an Owner
    review for Team Leaders as well; changing a reviewed item clears its reviews."""

    leader_reviewed_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    leader_reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    owner_reviewed_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    owner_reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    @declared_attr
    def leader_reviewed_by(cls) -> Mapped[User | None]:
        return relationship(foreign_keys=f"[{cls.__name__}.leader_reviewed_by_id]", lazy="selectin")

    @declared_attr
    def owner_reviewed_by(cls) -> Mapped[User | None]:
        return relationship(foreign_keys=f"[{cls.__name__}.owner_reviewed_by_id]", lazy="selectin")

    def clear_reviews(self) -> None:
        self.leader_reviewed_at = self.leader_reviewed_by_id = self.leader_reviewed_by = None
        self.owner_reviewed_at = self.owner_reviewed_by_id = self.owner_reviewed_by = None


class Project(Base):
    """A project and its budget. Amounts are whole US cents.

    Checks lock a project: a Leader check (by a Team Leader of its team) locks it for
    members, an Owner check locks it for Team Leaders and members as well.
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The person responsible for the project (not the Owner role). Members' projects are theirs.
    project_owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    category: Mapped[str] = mapped_column(String(20))
    # Required except for hourly projects, which may have no overall budget.
    total_budget_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    monthly_budget_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Stored exactly as entered: line breaks and spacing are part of the content.
    details: Mapped[str] = mapped_column(Text, default="")

    leader_checked_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    leader_checked_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    owner_checked_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    owner_checked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow, onupdate=utcnow)

    team: Mapped[Team | None] = relationship()
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
    project_owner: Mapped[User | None] = relationship(foreign_keys=[project_owner_id])
    leader_checked_by: Mapped[User | None] = relationship(foreign_keys=[leader_checked_by_id])
    owner_checked_by: Mapped[User | None] = relationship(foreign_keys=[owner_checked_by_id])
    payments: Mapped[list[ProjectPayment]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="(ProjectPayment.paid_on, ProjectPayment.id)",
    )
    codevelopers: Mapped[list[ProjectCodeveloper]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="ProjectCodeveloper.id"
    )
    revenue_forecasts: Mapped[list[ProjectRevenueForecast]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="(ProjectRevenueForecast.year, ProjectRevenueForecast.month)",
    )


class ProjectCodeveloper(Reviewable, Base):
    """Someone a project's income is shared with. At least one of nationality, name and
    ID is set; contact details are optional."""

    __tablename__ = "project_codevelopers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    nationality: Mapped[str] = mapped_column(String(100), default="")
    name: Mapped[str] = mapped_column(String(200), default="")
    external_id: Mapped[str] = mapped_column(String(100), default="")  # their ID, e.g. a platform username
    contact: Mapped[str] = mapped_column(String(300), default="")  # optional free text: email, phone, chat handle

    @property
    def label(self) -> str:
        return self.name or self.external_id or self.nationality


class ProjectPayment(Reviewable, Base):
    """One entry of a project's payment history: money received and how it was split.

    remaining = amount (total received) - my_share - the payouts to co-developers; never negative.
    """

    __tablename__ = "project_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    paid_on: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(300), default="")
    amount_cents: Mapped[int] = mapped_column(BigInteger)  # total received
    my_share_cents: Mapped[int] = mapped_column(BigInteger, default=0)  # the portion you received
    fund_location: Mapped[str] = mapped_column(String(200), default="")  # where the money is kept

    project: Mapped[Project] = relationship(back_populates="payments")
    payouts: Mapped[list[PaymentPayout]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="PaymentPayout.id"
    )

    @property
    def remaining_cents(self) -> int:
        return self.amount_cents - self.my_share_cents - sum(p.amount_cents for p in self.payouts)


class PaymentPayout(Base):
    """What a payment paid one co-developer."""

    __tablename__ = "payment_payouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("project_payments.id", ondelete="CASCADE"), index=True)
    codeveloper_id: Mapped[int] = mapped_column(ForeignKey("project_codevelopers.id", ondelete="CASCADE"), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)

    codeveloper: Mapped[ProjectCodeveloper] = relationship(lazy="selectin")


class ProjectRevenueForecast(Reviewable, Base):
    """The revenue a project is expected to bring in one calendar month (whole US cents)."""

    __tablename__ = "project_revenue_forecasts"
    __table_args__ = (UniqueConstraint("project_id", "year", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(SmallInteger)
    month: Mapped[int] = mapped_column(SmallInteger)  # 1-12
    amount_cents: Mapped[int] = mapped_column(BigInteger)
