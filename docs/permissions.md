# Permissions

## Roles

The roles are defined in `shared/enums.py` and ranked: **owner > team_leader > member**. A higher role has every permission of a lower one (`Role.at_least`).

| Role | Intended scope |
|---|---|
| `owner` | Whole organization, including creating teams, adding Team Leaders and destructive actions. Created at first start; belongs to no team. |
| `team_leader` | Their own team: adds plain members to it and resets those members' devices. |
| `member` | Their own profile, plus the projects and data they're assigned to. |

Accounts are only created by people with `members.add` (the Owner, Team Leaders, and anyone given it through a bundle); there's no self-registration. Whoever adds a member sets that member's initial password, and the member must change it at first sign-in.

## Permissions and role bundles

The catalog is in `shared/permissions.py`:

| Group | Permissions |
|---|---|
| Members | `members.view`, `members.add`, `members.edit`, `members.delete`, `members.team`, `members.promote`, `members.reset_device`, `members.assign_roles` |
| Teams | `teams.create`, `teams.rename` |
| Projects | `projects.view`, `projects.create`, `projects.edit`, `projects.delete`, `projects.check` |
| Revenue (enforced once the module exists) | `revenue.view`, `revenue.edit` |

A user's **effective permissions** are their base role's permissions plus those of every **role bundle** assigned to them.

- **Base roles:** the Owner has every permission. A Team Leader has all of Members, Projects and Revenue. A Member has `projects.view`.
- **Implied permission:** any `members.*` permission also grants `members.view`.

Rules:

1. **Defining bundles:** only the Owner creates, edits and deletes bundles, on the Roles page. Edits and deletions apply immediately to everyone holding the bundle.
2. **Assigning bundles:** this happens when a member is added, or later with **Edit roles**.
   - The Owner can assign any bundle to anyone except themselves; the Owner already has every permission.
   - Anyone else needs `members.assign_roles`, and can add or remove a bundle only if they hold **every** permission in it. So nobody can grant more than they have.
3. **Scope for non-owners:** a non-owner acts only on plain members of **their teams**, never on themselves or on Team Leaders. "Their teams" means every team a Team Leader leads (a Team Leader may lead several), or a member's own team. This applies to adding, editing, deleting, resetting devices and assigning bundles. `teams.*` permissions apply across the whole organization.
4. **Base roles.**
   - **The Owner** sets anyone's role (Member or Team Leader) in the Edit dialog and moves members freely between teams.
   - **Holders of `members.promote`** (Team Leaders by default) can make a plain member of one of their teams a Team Leader of that same team, so a team can have several leaders. Only the Owner turns a Team Leader back into a Member.
   - **Members without a team:** the Owner can add members with no team, or clear anyone's team.
   - **Team Leaders** must always lead at least one team. The Owner assigns them on the Teams tab (Manage → Add as leader); a plain member added as leader is promoted. Removing a leader's last team, or deleting it, makes them a plain member.
   - **Team membership (`members.team`)** lets a non-owner do two things: bring a plain member who has no team into their own team, or take a plain member out of their own team. The account stays, with no team. Such users also see members with no team in their list.
5. **Editing a member** (`members.edit`) covers name, email, active status and setting a new initial password. Changing the email, setting a password or disabling the account signs the member out. Nobody can disable themselves or set their own password this way.
6. **Deleting a member** (`members.delete`) is permanent; their device, sessions and bundles go with the account. The audit log keeps who it was. The Owner's account cannot be deleted.
7. **When changes take effect:** the server applies a change on the next request. The affected user's app shows new menus after their next token refresh (at most 30 minutes) or their next sign-in.

## Sign-in rules (every role, including the Owner)

1. **Device binding.** The first sign-in binds the account to that computer's device ID (a hash of its MAC address). Sign-ins from any other computer are refused until the binding is reset:
   - the Owner can reset anyone's binding;
   - a Team Leader can reset their own team's plain members;
   - the Owner's own binding is reset on the server with `python -m server.manage reset-device <email>`.
2. **Signed requests.** Every authenticated request carries an HMAC signature made with the device secret. See [api.md](api.md).
3. **First login.** An account with an initial password gets `403` from every endpoint except `/auth/me` and `/auth/change-password` until the password is changed. `get_current_user` enforces this, so every route that depends on it is covered.

## Enforcing in the API

```python
from fastapi import Depends
from server.app.core.permissions import require_permission, ensure_same_organization
from shared.permissions import Permission

@router.post("/members")
def invite_member(body: InviteRequest, user: User = Depends(require_permission(Permission.MEMBERS_ADD))):
    ...

@router.get("/projects/{project_id}")
def get_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = ProjectRepository(db).get(project_id)
    ensure_same_organization(user, project.organization_id)  # 404 across organizations
```

Rules:

1. **Check every protected route on the server.** The client hides UI the user can't use, but that's for convenience, not security.
2. **Scope every query to the caller's organization.** A resource from another organization returns `404`, not `403`, so IDs from other organizations are never confirmed.
3. **Record sensitive changes in `audit_logs`**, such as role changes, deletions and revenue edits, through `AuditRepository.record`.

## Matrix

Defaults per base role. Bundles can grant a Member or Team Leader more, within the scope rules above.

| Action | member | team leader | owner |
|---|:-:|:-:|:-:|
| Sign in, reset or change own password | ✓ | ✓ | ✓ |
| View own profile and own team | ✓ | ✓ | ✓ |
| List members | | own team | all |
| Add members | | to own team, as member | any team, as member or team leader |
| Edit a member (name, email, active, new initial password) | | own team's members | anyone (own name and email only for themselves) |
| Add a member with no team, or clear a member's team | | | ✓ |
| Bring a member with no team into the team / take a member out of it | | own team | ✓ |
| Move a member between teams | | | ✓ |
| Delete a member | | own team's members | anyone but the Owner |
| Reset a member's device | | own team's members | anyone but themselves (CLI for that) |
| Assign role bundles | | own team's members, bundles within own permissions | anyone but themselves |
| Make a team member a Team Leader (of the same team) | | own teams' members | ✓ |
| Make a Team Leader a Member | | | ✓ |
| Create, rename teams | | | ✓ |
| Delete teams (members keep their accounts with no team; its Team Leaders become members) | | | ✓ |
| Define role bundles | | | ✓ |
| See projects ("own" = they are its project owner) | own | own teams' and own | all |
| Add, edit, delete projects (incl. payment history) | own, until a Leader or Owner check | own teams' and own, until an Owner check | all, always |
| Designate the project owner | always themselves | themselves or anyone on their teams | anyone |
| Check projects (locks them for those below) | | own teams' (Leader check) | all (Owner check) |
| *Planned:* view/edit revenue | | ✓ | ✓ |

Update this table as each module lands.
