from __future__ import annotations

import re
from datetime import date, datetime

from PySide6.QtCore import Property, QObject, Signal, Slot

from client.api.client import ApiResult
from client.api.members_api import MembersApi
from client.viewmodels.auth_viewmodel import AuthViewModel
from shared.permissions import CATALOG

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Team choices from QML: NO_TEAM is an explicit "No team"; UNCHANGED/unset is "not chosen".
NO_TEAM = 0
UNCHANGED = -1
ALL_TEAMS = -1  # team filter: no restriction
PAGE_SIZES = (10, 20, 50, 100)
GAP = -1  # in pageNumbers: an ellipsis between page numbers
DATE_FORMAT = "YYYY-MM-DD"


def _parse_day(text: str) -> date | None:
    """A complete YYYY-MM-DD date, or None. Raises ValueError for a complete but invalid one."""
    text = text.strip()
    if len(text) < len(DATE_FORMAT):
        return None  # still being typed (or empty): no bound yet
    return date.fromisoformat(text)


def _registered_on(member: dict) -> date | None:
    """The member's registration day in the local time zone."""
    raw = member.get("created_at")
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone().date()

# For QML: [{group, permissions: [{value, label, description}]}]
_CATALOG = [
    {"group": group, "permissions": [{"value": p.value, "label": label, "description": text} for p, label, text in items]}
    for group, items in CATALOG
]


class MembersViewModel(QObject):
    """Teams, members and role bundles, exposed to QML. What each user may do follows their permissions."""

    changed = Signal()
    stateChanged = Signal()
    memberAdded = Signal(str)
    teamCreated = Signal(str)
    teamRenamed = Signal(str)
    teamDeleted = Signal(str)
    bundleSaved = Signal()
    memberRolesSaved = Signal()
    memberSaved = Signal()
    memberDeleted = Signal()
    filterChanged = Signal()

    def __init__(self, auth: AuthViewModel, api: MembersApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._auth = auth
        self._api = api
        self._teams: list[dict] = []
        self._members: list[dict] = []
        self._bundles: list[dict] = []
        self._busy = False
        self._error = ""
        self._error_fields: list[str] = []
        self._notice = ""
        # Member list filters. They run on the already loaded (and server-scoped) list.
        self._filter_text = ""
        self._filter_team = ALL_TEAMS
        self._filter_role = ""
        self._filter_from = ""
        self._filter_to = ""
        # Pagination of the filtered list (page is 0-based).
        self._page_size = PAGE_SIZES[0]
        self._page = 0
        auth.sessionChanged.connect(self._on_session_changed)
        self.changed.connect(self.filterChanged)

    # ------------------------------------------------------------------ props
    @Property("QVariantList", notify=changed)
    def teams(self) -> list[dict]:
        return self._teams

    @Property("QVariantList", notify=changed)
    def members(self) -> list[dict]:
        return self._members

    # --------------------------------------------------------------- filters
    @Property(str, notify=filterChanged)
    def filterText(self) -> str:
        return self._filter_text

    @Property(int, notify=filterChanged)
    def filterTeamId(self) -> int:
        return self._filter_team

    @Property(str, notify=filterChanged)
    def filterRole(self) -> str:
        return self._filter_role

    @Property(str, notify=filterChanged)
    def filterFrom(self) -> str:
        return self._filter_from

    @Property(str, notify=filterChanged)
    def filterTo(self) -> str:
        return self._filter_to

    @Property(bool, notify=filterChanged)
    def filterActive(self) -> bool:
        return bool(
            self._filter_text.strip() or self._filter_team != ALL_TEAMS or self._filter_role
            or self._filter_from.strip() or self._filter_to.strip()
        )

    def _date_range(self) -> tuple[date | None, date | None, list[str], str]:
        """(from, to, invalid fields, message). Invalid bounds are not applied."""
        start = end = None
        bad: list[str] = []
        try:
            start = _parse_day(self._filter_from)
        except ValueError:
            bad.append("dateFrom")
        try:
            end = _parse_day(self._filter_to)
        except ValueError:
            bad.append("dateTo")
        if bad:
            return start, end, bad, f"Enter dates as {DATE_FORMAT}."
        if start and end and start > end:
            return None, None, ["dateFrom", "dateTo"], "The start date is after the end date."
        return start, end, [], ""

    @Property("QStringList", notify=filterChanged)
    def filterErrorFields(self) -> list[str]:
        return self._date_range()[2]

    @Property(str, notify=filterChanged)
    def filterError(self) -> str:
        return self._date_range()[3]

    @Property("QVariantList", notify=filterChanged)
    def filteredMembers(self) -> list[dict]:
        text = self._filter_text.strip().casefold()
        start, end, _, _ = self._date_range()
        result = []
        for m in self._members:
            if text and text not in (m.get("full_name") or "").casefold() and text not in m.get("email", "").casefold():
                continue
            if self._filter_role and m.get("role") != self._filter_role:
                continue
            led = [t["id"] for t in m.get("led_teams") or []]
            if self._filter_team == NO_TEAM:
                if m.get("role") == "owner" or m.get("team_id") or led:
                    continue
            elif self._filter_team != ALL_TEAMS and m.get("team_id") != self._filter_team and self._filter_team not in led:
                continue
            if start or end:
                day = _registered_on(m)
                if day is None or (start and day < start) or (end and day > end):
                    continue
            result.append(m)
        return result

    def _refilter(self) -> None:
        """A filter changed: show the first page of the new result."""
        self._page = 0
        self.filterChanged.emit()

    @Slot(str)
    def setFilterText(self, text: str) -> None:
        self._filter_text = text
        self._refilter()

    @Slot(int)
    def setFilterTeam(self, team_id: int) -> None:
        self._filter_team = team_id
        self._refilter()

    @Slot(str)
    def setFilterRole(self, role: str) -> None:
        self._filter_role = role
        self._refilter()

    @Slot(str, str)
    def setFilterDates(self, start: str, end: str) -> None:
        self._filter_from, self._filter_to = start, end
        self._refilter()

    @Slot()
    def clearFilters(self) -> None:
        self._filter_text, self._filter_team, self._filter_role = "", ALL_TEAMS, ""
        self._filter_from = self._filter_to = ""
        self._refilter()

    # ------------------------------------------------------------ pagination
    @Property("QVariantList", constant=True)
    def pageSizes(self) -> list[int]:
        return list(PAGE_SIZES)

    @Property(int, notify=filterChanged)
    def pageSize(self) -> int:
        return self._page_size

    @Property(int, notify=filterChanged)
    def pageCount(self) -> int:
        return max(1, -(-len(self.filteredMembers) // self._page_size))

    @Property(int, notify=filterChanged)
    def pageIndex(self) -> int:
        """The current page, 0-based; kept in range when the list shrinks (e.g. after a refresh)."""
        return min(self._page, self.pageCount - 1)

    @Property("QVariantList", notify=filterChanged)
    def pagedMembers(self) -> list[dict]:
        start = self.pageIndex * self._page_size
        return self.filteredMembers[start:start + self._page_size]

    @Property(str, notify=filterChanged)
    def pageRange(self) -> str:
        """e.g. "11–20 of 37"; empty when there is nothing to show."""
        total = len(self.filteredMembers)
        if not total:
            return ""
        start = self.pageIndex * self._page_size
        return f"{start + 1}–{min(start + self._page_size, total)} of {total}"

    @Property("QVariantList", notify=filterChanged)
    def pageNumbers(self) -> list[int]:
        """1-based page numbers to show, with GAP (-1) for skipped runs: 1 … 4 5 6 … 12."""
        count, current = self.pageCount, self.pageIndex + 1
        shown = sorted({1, count, current - 1, current, current + 1} & set(range(1, count + 1)))
        result: list[int] = []
        for n in shown:
            if result and n - result[-1] > 1:
                result.append(GAP) if n - result[-1] > 2 else result.append(n - 1)
            result.append(n)
        return result

    @Slot(int)
    def setPageSize(self, size: int) -> None:
        if size in PAGE_SIZES and size != self._page_size:
            # Keep the first row on screen in view.
            first = self.pageIndex * self._page_size
            self._page_size = size
            self._page = first // size
            self.filterChanged.emit()

    @Slot(int)
    def setPage(self, index: int) -> None:
        index = max(0, min(index, self.pageCount - 1))
        if index != self.pageIndex:
            self._page = index
            self.filterChanged.emit()

    @Slot()
    def nextPage(self) -> None:
        self.setPage(self.pageIndex + 1)

    @Slot()
    def previousPage(self) -> None:
        self.setPage(self.pageIndex - 1)

    @Property("QVariantList", notify=changed)
    def bundles(self) -> list[dict]:
        return self._bundles

    @Property("QVariantList", constant=True)
    def permissionCatalog(self) -> list[dict]:
        return _CATALOG

    @Property("QVariantList", notify=changed)
    def assignableBundleIds(self) -> list[int]:
        """Bundles this user may give or take away: all for the Owner, otherwise only
        those whose permissions they hold (and only with `members.assign_roles`)."""
        if self._auth.isOwner:
            return [b["id"] for b in self._bundles]
        if not self._auth.has("members.assign_roles"):
            return []
        held = set(self._auth.permissions)
        return [b["id"] for b in self._bundles if set(b["permissions"]) <= held]

    @Slot("QVariant", result=bool)
    def canEditRoles(self, member: dict) -> bool:
        if member.get("role") == "owner":
            return False
        if self._auth.isOwner:
            return True
        return self._in_my_scope(member, "members.assign_roles")

    def _in_my_scope(self, member: dict, permission: str) -> bool:
        """Non-owners act only on plain members of their teams, never themselves."""
        return (
            self._auth.has(permission)
            and member.get("role") == "member"
            and member.get("team_id") in self._auth.scopeTeamIds
            and member.get("email") != self._auth.userEmail
        )

    @Property("QVariantList", notify=changed)
    def scopeTeams(self) -> list[dict]:
        """The teams this user acts on, as {id, name}."""
        scope = set(self._auth.scopeTeamIds)
        return [t for t in self._teams if t["id"] in scope]

    @Slot("QVariant", result=bool)
    def canEditMember(self, member: dict) -> bool:
        return self._auth.isOwner or self._in_my_scope(member, "members.edit")

    @Slot("QVariant", result=bool)
    def canDeleteMember(self, member: dict) -> bool:
        if member.get("role") == "owner":
            return False
        return self._auth.isOwner or self._in_my_scope(member, "members.delete")

    @Slot("QVariant", result=bool)
    def canBringIntoTeam(self, member: dict) -> bool:
        """Non-owners with members.team: a plain member with no team can join one of their teams."""
        return (
            not self._auth.isOwner
            and self._auth.has("members.team")
            and bool(self._auth.scopeTeamIds)
            and member.get("role") == "member"
            and not member.get("team_id")
        )

    @Slot("QVariant", result=bool)
    def canTakeOutOfTeam(self, member: dict) -> bool:
        return not self._auth.isOwner and self._in_my_scope(member, "members.team")

    @Slot("QVariant", result=bool)
    def canResetDevice(self, member: dict) -> bool:
        # Resetting your own device would sign you out; the Owner uses `manage reset-device` instead.
        if not member.get("device_registered") or member.get("email") == self._auth.userEmail:
            return False
        if self._auth.isOwner:
            return True
        return (
            self._auth.has("members.reset_device")
            and member.get("role") == "member"
            and member.get("team_id") in self._auth.scopeTeamIds
        )

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

    def _call(self, method, *args, on_ok, fields_by_status: dict[int, list[str]] | None = None) -> None:
        self._set_state(True)

        def done(result: ApiResult) -> None:
            if result.ok:
                self._set_state(False)
                on_ok(result.data)
            else:
                fields = (fields_by_status or {}).get(result.status, [])
                if "team" in result.error.lower() and result.status in (403, 404, 422):
                    fields = ["team"]  # e.g. "A Team Leader must belong to a team."
                self._set_state(False, result.error, fields)

        method(self._auth.serverUrl, self._auth.access_token(), *args, done)

    def _on_session_changed(self) -> None:
        if not self._auth.loggedIn:
            self._teams, self._members, self._bundles = [], [], []
            self.changed.emit()
            self._set_state(False)

    # ------------------------------------------------------------------ slots
    @Slot()
    def refresh(self) -> None:
        """Reload teams, members and role bundles. Leaves the current message on screen."""
        if not self._auth.loggedIn:
            return
        server, token = self._auth.serverUrl, self._auth.access_token()
        self._set_busy(True)

        def got_teams(result: ApiResult) -> None:
            if not result.ok:
                self._set_state(False, result.error)
                return
            self._teams = result.data.get("items", [])
            self.changed.emit()
            if not self._auth.canManageMembers:
                self._set_busy(False)
                return
            self._api.list_members(server, token, got_members)

        def got_members(result: ApiResult) -> None:
            if not result.ok:
                self._set_state(False, result.error)
                return
            self._members = result.data.get("items", [])
            self.changed.emit()
            self._api.list_bundles(server, token, got_bundles)

        def got_bundles(result: ApiResult) -> None:
            if not result.ok:
                self._set_state(False, result.error)
                return
            self._bundles = result.data.get("items", [])
            self.changed.emit()
            self._set_busy(False)

        self._api.list_teams(server, token, got_teams)

    @Slot(str)
    def createTeam(self, name: str) -> None:
        name = " ".join(name.split())
        if not name:
            self._set_state(False, "Enter a team name.", ["teamName"])
            return

        def created(team: dict) -> None:
            self.teamCreated.emit(team["name"])
            self._set_state(False, notice=f"Team “{team['name']}” created.")
            self.refresh()

        self._call(self._api.create_team, name, on_ok=created, fields_by_status={409: ["teamName"], 422: ["teamName"]})

    @Slot(int, str)
    def renameTeam(self, team_id: int, name: str) -> None:
        name = " ".join(name.split())
        if not name:
            self._set_state(False, "Enter a team name.", ["teamName"])
            return

        def renamed(team: dict) -> None:
            self.teamRenamed.emit(team["name"])
            self._set_state(False, notice=f"Team renamed to “{team['name']}”.")
            self.refresh()

        self._call(self._api.rename_team, team_id, name, on_ok=renamed, fields_by_status={409: ["teamName"]})

    @Slot("QVariant")
    def deleteTeam(self, team: dict) -> None:
        """Owner only: the team's members stay with no team; its Team Leaders become members."""

        def deleted(data: dict) -> None:
            self.teamDeleted.emit(team["name"])
            message = data.get("message", "Team deleted.")
            self._set_state(False, notice=message.replace("Team deleted.", f"Team “{team['name']}” deleted.", 1))
            self.refresh()

        self._call(self._api.delete_team, team["id"], on_ok=deleted)

    @Slot(str, str, int, str, str, "QVariantList")
    def addMember(
        self, email: str, full_name: str, team_id: int, role: str, initial_password: str, bundle_ids: list
    ) -> None:
        email = email.strip().lower()
        owner = self._auth.isOwner
        if not owner:
            role = "member"
            scope = self._auth.scopeTeamIds
            if team_id <= 0 and len(scope) == 1:
                team_id = scope[0]  # their only team
        problem, fields = "", []
        if not _EMAIL_RE.match(email):
            problem, fields = "Enter the member's email address.", ["email"]
        elif team_id == UNCHANGED or (team_id == NO_TEAM and not owner):
            problem, fields = ("Select a team, or No team." if owner else "Select a team."), ["team"]
        elif not owner and team_id not in self._auth.scopeTeamIds:
            problem, fields = "Select one of your teams.", ["team"]
        elif team_id == NO_TEAM and role == "team_leader":
            problem, fields = "A Team Leader must belong to a team.", ["team"]
        elif not initial_password:
            problem, fields = "Set an initial password for the member.", ["password"]
        if problem:
            self._set_state(False, problem, fields)
            return

        body = {
            "email": email,
            "full_name": full_name.strip(),
            "team_id": team_id if team_id > 0 else None,
            "role": role,
            "initial_password": initial_password,
            "role_bundle_ids": [int(i) for i in bundle_ids],
        }

        def added(member: dict) -> None:
            self.memberAdded.emit(member["email"])
            self._set_state(
                False,
                notice=f"{member['email']} added. They must change the initial password at first sign-in.",
            )
            self.refresh()

        self._call(
            self._api.add_member, body, on_ok=added,
            fields_by_status={404: ["team"], 409: ["email"], 422: ["password"]},
        )

    @Slot(int, str, "QVariantList")
    def saveMemberRoles(self, user_id: int, role: str, bundle_ids: list) -> None:
        """Set a member's role bundles, and base role too when `role` is given (Owner only)."""
        body: dict = {"role_bundle_ids": [int(i) for i in bundle_ids]}
        if role and self._auth.isOwner:
            body["role"] = role

        def saved(member: dict) -> None:
            self.memberRolesSaved.emit()
            self._set_state(False, notice=f"Roles updated for {member['email']}.")
            self.refresh()

        self._call(self._api.update_member, user_id, body, on_ok=saved)

    @Slot("QVariant", str, str, int, bool, str)
    def saveMember(
        self, member: dict, full_name: str, email: str, team_id: int, is_active: bool, new_password: str
    ) -> None:
        """Send only what changed. `team_id`: UNCHANGED (-1) leaves it, NO_TEAM (0) clears it
        (Owner only here); an empty `new_password` leaves the password."""
        email = email.strip().lower()
        if not _EMAIL_RE.match(email):
            self._set_state(False, "Enter a valid email address.", ["email"])
            return
        body: dict = {}
        if full_name.strip() != member.get("full_name", ""):
            body["full_name"] = full_name.strip()
        if email != member.get("email"):
            body["email"] = email
        if team_id != UNCHANGED and self._auth.isOwner and team_id != (member.get("team_id") or NO_TEAM):
            body["team_id"] = team_id if team_id > 0 else None
        if is_active != member.get("is_active", True):
            body["is_active"] = is_active
        if new_password:
            body["new_password"] = new_password
        if not body:
            self.memberSaved.emit()
            return
        own_email_changed = member.get("email") == self._auth.userEmail and "email" in body

        def saved(updated: dict) -> None:
            self.memberSaved.emit()
            if own_email_changed:
                # Requests are signed with the email, so this session cannot continue.
                self._auth.sign_out_with_message(f"Your email is now {updated['email']}. Sign in with it.")
                return
            self._set_state(False, notice=f"Saved changes to {updated['email']}.")
            self.refresh()

        self._call(
            self._api.update_member, member["id"], body, on_ok=saved,
            fields_by_status={409: ["email"], 404: ["team"], 422: ["password"]},
        )

    @Slot("QVariant", int)
    def setMemberTeam(self, member: dict, team_id: int) -> None:
        """Move a member into a team, or out of theirs with NO_TEAM."""
        target = team_id if team_id > 0 else None
        name = member.get("full_name") or member["email"]

        def moved(updated: dict) -> None:
            if updated.get("team_name"):
                notice = f"{name} joined {updated['team_name']}."
            else:
                notice = f"{name} was taken out of the team. Their account is kept."
            self._set_state(False, notice=notice)
            self.refresh()

        self._call(self._api.update_member, member["id"], {"team_id": target}, on_ok=moved)

    @Slot(int, "QVariant")
    def addTeamLeader(self, team_id: int, member: dict) -> None:
        """Owner: make someone a leader of this team (a member is promoted to Team Leader)."""
        name = member.get("full_name") or member["email"]

        def added(_: dict) -> None:
            team = next((t["name"] for t in self._teams if t["id"] == team_id), "the team")
            self._set_state(False, notice=f"{name} now leads {team}.")
            self.refresh()

        self._call(self._api.add_team_leader, team_id, member["id"], on_ok=added)

    @Slot(int, "QVariant")
    def removeTeamLeader(self, team_id: int, member: dict) -> None:
        """Owner: stop someone leading this team; leading no team any more makes them a member."""
        name = member.get("full_name") or member.get("email") or member.get("name", "")

        def removed(updated: dict) -> None:
            team = next((t["name"] for t in self._teams if t["id"] == team_id), "the team")
            suffix = " They lead no team any more, so they are now a Member." if updated["role"] == "member" else ""
            self._set_state(False, notice=f"{name} no longer leads {team}.{suffix}")
            self.refresh()

        self._call(self._api.remove_team_leader, team_id, member["id"], on_ok=removed)

    @Slot("QVariant")
    def deleteMember(self, member: dict) -> None:
        def deleted(_: dict) -> None:
            self.memberDeleted.emit()
            self._set_state(False, notice=f"{member['email']} was deleted.")
            self.refresh()

        self._call(self._api.delete_member, member["id"], on_ok=deleted)

    # -------------------------------------------------------- role bundles
    def _bundle_body(self, name: str, description: str, permissions: list) -> dict | None:
        name = " ".join(name.split())
        if not name:
            self._set_state(False, "Enter a bundle name.", ["bundleName"])
            return None
        if not permissions:
            self._set_state(False, "Choose at least one permission.", ["bundlePermissions"])
            return None
        return {"name": name, "description": description.strip(), "permissions": [str(p) for p in permissions]}

    @Slot(str, str, "QStringList")
    def createBundle(self, name: str, description: str, permissions: list) -> None:
        if (body := self._bundle_body(name, description, permissions)) is None:
            return

        def created(bundle: dict) -> None:
            self.bundleSaved.emit()
            self._set_state(False, notice=f"Role bundle “{bundle['name']}” created.")
            self.refresh()

        self._call(self._api.create_bundle, body, on_ok=created, fields_by_status={409: ["bundleName"]})

    @Slot(int, str, str, "QStringList")
    def updateBundle(self, bundle_id: int, name: str, description: str, permissions: list) -> None:
        if (body := self._bundle_body(name, description, permissions)) is None:
            return

        def updated(bundle: dict) -> None:
            self.bundleSaved.emit()
            self._set_state(False, notice=f"Role bundle “{bundle['name']}” saved.")
            self.refresh()

        self._call(self._api.update_bundle, bundle_id, body, on_ok=updated, fields_by_status={409: ["bundleName"]})

    @Slot(int)
    def deleteBundle(self, bundle_id: int) -> None:
        name = next((b["name"] for b in self._bundles if b["id"] == bundle_id), "")

        def deleted(_: dict) -> None:
            self._set_state(False, notice=f"Role bundle “{name}” deleted.")
            self.refresh()

        self._call(self._api.delete_bundle, bundle_id, on_ok=deleted)

    @Slot(int)
    def resetDevice(self, user_id: int) -> None:
        def reset(member: dict) -> None:
            self._set_state(
                False, notice=f"Device registration reset for {member['email']}. Their next sign-in registers the PC used."
            )
            self.refresh()

        self._call(self._api.reset_device, user_id, on_ok=reset)

    @Slot(str)
    def fieldEdited(self, field: str) -> None:
        if field in self._error_fields:
            self._set_state(self._busy)

    @Slot()
    def clearMessages(self) -> None:
        self._set_state(self._busy)
