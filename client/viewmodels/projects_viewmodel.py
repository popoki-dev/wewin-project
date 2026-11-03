from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Property, QObject, Signal, Slot

from client.api.client import ApiResult
from client.api.projects_api import ProjectsApi
from client.viewmodels.auth_viewmodel import AuthViewModel
from shared.projects import CATEGORY_LABELS, DETAILS_MAX_LENGTH, MAX_AMOUNT_CENTS, TITLE_MAX_LENGTH

_CATEGORIES = [{"value": c.value, "text": label} for c, label in CATEGORY_LABELS.items()]


def parse_money(text: str) -> int | None:
    """Dollars as typed ("1,200", "$1200.50") to cents. None if blank; ValueError if not money."""
    text = text.strip().replace(",", "").replace("$", "").strip()
    if not text:
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValueError("not a number") from None
    if not amount.is_finite() or amount < 0 or amount * 100 > MAX_AMOUNT_CENTS:
        raise ValueError("not an amount")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("more than two decimals")
    return int(amount * 100)


def format_money(cents: int | None) -> str:
    """Cents to "$1,200.50" (blank for None)."""
    if cents is None:
        return ""
    return f"${cents // 100:,}.{cents % 100:02d}"


def _parse_day(text: str, required: bool) -> date | None:
    text = text.strip()
    if not text:
        if required:
            raise ValueError("missing")
        return None
    return date.fromisoformat(text)


class ProjectsViewModel(QObject):
    """Projects and their payment history, exposed to QML. What each user may do with a
    project comes from the server (each project's `access`)."""

    changed = Signal()
    stateChanged = Signal()
    projectSaved = Signal()
    projectDeleted = Signal()

    def __init__(self, auth: AuthViewModel, api: ProjectsApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._auth = auth
        self._api = api
        self._projects: list[dict] = []
        self._busy = False
        self._error = ""
        self._error_fields: list[str] = []
        self._notice = ""
        auth.sessionChanged.connect(self._on_session_changed)

    # ------------------------------------------------------------------ props
    @Property("QVariantList", notify=changed)
    def projects(self) -> list[dict]:
        return self._projects

    @Property("QVariantList", constant=True)
    def categories(self) -> list[dict]:
        return _CATEGORIES

    @Property(bool, notify=stateChanged)
    def canCreate(self) -> bool:
        return self._auth.has("projects.create")

    @Property(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=stateChanged)
    def errorMessage(self) -> str:
        return self._error

    @Property("QStringList", notify=stateChanged)
    def errorFields(self) -> list[str]:
        return self._error_fields

    @Property(str, notify=stateChanged)
    def notice(self) -> str:
        return self._notice

    @Property(int, constant=True)
    def titleMaxLength(self) -> int:
        return TITLE_MAX_LENGTH

    @Property(int, constant=True)
    def detailsMaxLength(self) -> int:
        return DETAILS_MAX_LENGTH

    # ---------------------------------------------------------------- helpers
    def _set_state(self, busy: bool, error: str = "", fields: list[str] | None = None, notice: str = "") -> None:
        self._busy = busy
        self._error = error
        self._error_fields = (fields or []) if error else []
        self._notice = notice
        self.stateChanged.emit()

    def _set_busy(self, busy: bool) -> None:
        """Change only the busy flag, keeping any message on screen."""
        self._busy = busy
        self.stateChanged.emit()

    def _call(self, method, *args, on_ok) -> None:
        self._set_state(True)

        def done(result: ApiResult) -> None:
            if result.ok:
                self._set_state(False)
                on_ok(result.data)
            else:
                self._set_state(False, result.error, self._fields_for(result.error))

        method(self._auth.serverUrl, self._auth.access_token(), *args, done)

    @staticmethod
    def _fields_for(message: str) -> list[str]:
        text = message.lower()
        for word, field in (("title", "title"), ("completion", "endDate"), ("start", "startDate"),
                            ("team", "team"), ("payment", "payments"), ("budget", "totalBudget")):
            if word in text:
                return [field]
        return []

    def _on_session_changed(self) -> None:
        if not self._auth.loggedIn:
            self._projects = []
            self.changed.emit()
            self._set_state(False)
        else:
            self.stateChanged.emit()  # canCreate follows the user's permissions

    # ------------------------------------------------------------------ slots
    @Slot(result=str)
    def today(self) -> str:
        """The default start date: today, in the local time zone."""
        return date.today().isoformat()

    @Slot("QVariant", result=str)
    def money(self, cents) -> str:
        return format_money(None if cents is None else int(cents))

    @Slot("QVariant", result=str)
    def moneyInput(self, cents) -> str:
        """Cents as an editable amount ("1200.50"), blank for none."""
        if cents is None:
            return ""
        cents = int(cents)
        return f"{cents // 100}.{cents % 100:02d}"

    @Slot(str, result=str)
    def categoryLabel(self, value: str) -> str:
        return next((c["text"] for c in _CATEGORIES if c["value"] == value), value)

    @Slot()
    def refresh(self) -> None:
        """Reload the list. Leaves the current message on screen."""
        if not self._auth.loggedIn or not self._auth.has("projects.view"):
            return
        self._set_busy(True)

        def got(result: ApiResult) -> None:
            if not result.ok:
                self._set_state(False, result.error)
                return
            self._projects = result.data.get("items", [])
            self.changed.emit()
            self._set_busy(False)

        self._api.list(self._auth.serverUrl, self._auth.access_token(), got)

    @Slot(int, str, str, str, str, str, str, str, int, "QVariantList")
    def saveProject(
        self, project_id: int, title: str, start: str, end: str, category: str,
        total_budget: str, monthly_budget: str, details: str, team_id: int, payments: list,
    ) -> None:
        """Create (project_id 0) or update a project. Amounts are dollars as typed;
        `team_id` 0 means no team (the server files members' projects itself)."""
        problem, fields = "", []
        body: dict = {}
        try:
            body["title"] = " ".join(title.split())
            if not body["title"]:
                raise ValueError
        except ValueError:
            problem, fields = "Enter a project title.", ["title"]
        if not problem:
            try:
                body["start_date"] = _parse_day(start, required=True).isoformat()
            except ValueError:
                problem, fields = "Enter the start date as YYYY-MM-DD.", ["startDate"]
        if not problem:
            try:
                end_day = _parse_day(end, required=False)
                body["end_date"] = end_day.isoformat() if end_day else None
                if end_day and end_day < date.fromisoformat(body["start_date"]):
                    problem, fields = "The completion date cannot be before the start date.", ["endDate"]
            except ValueError:
                problem, fields = "Enter the completion date as YYYY-MM-DD, or leave it blank.", ["endDate"]
        if not problem and category not in {c["value"] for c in _CATEGORIES}:
            problem, fields = "Choose a category.", ["category"]
        if not problem:
            try:
                body["total_budget_cents"] = parse_money(total_budget)
                if body["total_budget_cents"] is None and category != "hourly":
                    problem, fields = "Enter the total budget (only hourly projects may leave it blank).", ["totalBudget"]
            except ValueError:
                problem, fields = "Enter the total budget in dollars, e.g. 12000 or 12,000.50.", ["totalBudget"]
        if not problem:
            try:
                body["monthly_budget_cents"] = parse_money(monthly_budget)
            except ValueError:
                problem, fields = "Enter the monthly budget in dollars, or leave it blank.", ["monthlyBudget"]
        if not problem:
            body["payments"], problem = self._payments_body(payments)
            if problem:
                fields = ["payments"]
        if problem:
            self._set_state(False, problem, fields)
            return

        body["category"] = category
        body["details"] = details  # exactly as typed: line breaks and spacing are content
        body["team_id"] = team_id if team_id > 0 else None

        def saved(project: dict) -> None:
            self.projectSaved.emit()
            self._set_state(False, notice=f"Project “{project['title']}” saved.")
            self.refresh()

        if project_id > 0:
            self._call(self._api.update, project_id, body, on_ok=saved)
        else:
            self._call(self._api.create, body, on_ok=saved)

    @staticmethod
    def _payments_body(rows: list) -> tuple[list[dict], str]:
        """Payment rows from the dialog ({id, paid_on, description, amount}) for the API."""
        result = []
        for n, row in enumerate(rows, start=1):
            row = dict(row)
            try:
                day = _parse_day(str(row.get("paid_on", "")), required=True)
            except ValueError:
                return [], f"Payment {n}: enter the date as YYYY-MM-DD."
            try:
                cents = parse_money(str(row.get("amount", "")))
            except ValueError:
                return [], f"Payment {n}: enter the amount in dollars."
            if not cents:
                return [], f"Payment {n}: enter an amount above zero."
            entry = {"paid_on": day.isoformat(), "description": str(row.get("description", "")).strip(),
                     "amount_cents": cents}
            if int(row.get("id") or 0) > 0:
                entry["id"] = int(row["id"])
            result.append(entry)
        return result, ""

    @Slot("QVariant")
    def deleteProject(self, project: dict) -> None:
        def deleted(_: dict) -> None:
            self.projectDeleted.emit()
            self._set_state(False, notice=f"Project “{project['title']}” deleted.")
            self.refresh()

        self._call(self._api.delete, int(project["id"]), on_ok=deleted)

    @Slot("QVariant")
    def checkProject(self, project: dict) -> None:
        def checked(_: dict) -> None:
            self._set_state(False, notice=f"“{project['title']}” checked.")
            self.refresh()

        self._call(self._api.check, int(project["id"]), on_ok=checked)

    @Slot("QVariant")
    def uncheckProject(self, project: dict) -> None:
        """Remove the check this user may remove: the Owner's own, else the Leader check."""
        level = "owner" if self._auth.isOwner and project.get("owner_check") else "leader"

        def unchecked(_: dict) -> None:
            self._set_state(False, notice=f"Check removed from “{project['title']}”.")
            self.refresh()

        self._call(self._api.uncheck, int(project["id"]), level, on_ok=unchecked)

    @Slot(str)
    def fieldEdited(self, field: str) -> None:
        if field in self._error_fields:
            self._set_state(self._busy)

    @Slot()
    def clearMessages(self) -> None:
        self._set_state(self._busy)
