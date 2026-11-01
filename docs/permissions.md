# Permissions

## Roles

The roles are defined in `shared/enums.py` and ranked: **owner > admin > member**. A higher role has every permission of a lower one (`Role.at_least`).

| Role | Intended scope |
|---|---|
| `owner` | Whole organization, including billing-level and destructive actions and managing admins. Created at first start. |
| `admin` | Day-to-day management of members, teams, projects and revenue. |
| `member` | Their own profile, plus the projects and data they're assigned to. |

## Enforcing in the API

```python
from fastapi import Depends
from server.app.core.permissions import require_role, ensure_same_organization
from shared.enums import Role

@router.post("/members")
def invite_member(body: InviteRequest, user: User = Depends(require_role(Role.ADMIN))):
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

| Action | member | admin | owner |
|---|:-:|:-:|:-:|
| Sign in, reset own password | ✓ | ✓ | ✓ |
| View own profile | ✓ | ✓ | ✓ |
| *Planned:* view teams/projects they belong to | ✓ | ✓ | ✓ |
| *Planned:* invite/deactivate members, manage teams & projects | | ✓ | ✓ |
| *Planned:* view/edit revenue | | ✓ | ✓ |
| *Planned:* promote/demote admins, organization settings | | | ✓ |

Update this table as each module lands.
