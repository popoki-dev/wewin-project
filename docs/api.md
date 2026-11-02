# API

Base path `/api`. JSON in and out. Path constants live in `shared/api_contracts.py`.

**Errors** always have the shape `{"detail": "<human-readable message>"}`, including validation errors (422). The client shows `detail` as-is.

**Authentication:** protected endpoints (🔒) need both of these:

1. `Authorization: Bearer <access_token>`.
2. **A device signature.** This is required on 🔒 endpoints and on `/auth/refresh`. It's defined in `shared/device_signature.py`:

| Header | Value |
|---|---|
| `X-WeWin-Device` | Device ID: `sha256("WeWin-device:" + MAC)` as 64 hex characters. It's the same value as `device_id` at login. |
| `X-WeWin-Timestamp` | Current UTC time, e.g. `2026-11-02T09:30:00.123Z`. Must be within 5 minutes of the server clock. |
| `X-WeWin-Nonce` | 16–64 random URL-safe characters. Each value is accepted once per device. |
| `X-WeWin-Signature` | `hex(HMAC-SHA256(device_secret, device_id \n email \n timestamp \n nonce \n METHOD \n path))` |

The `device_secret` comes from the login response. It changes on every sign-in.

Failures return `401`:
- **Missing, wrong or replayed signature:** `Device verification failed. Please sign in again.`
- **Clock more than 5 minutes off:** a message asking the user to correct the computer's clock.

An account that still has its initial password gets `403 Change your password to continue.` from every 🔒 endpoint except `/auth/me` and `/auth/change-password`.

In development, interactive docs are at `/docs`; they're disabled in production.

## Meta

### `GET /api/health`
`200 {"status": "ok", "app": "WeWin", "version": "0.2.0", "database": "ok" | "unavailable"}`

The client uses `app == "WeWin"` to confirm the server address points at a WeWin server.

## Auth

### `POST /api/auth/login`
```json
{"email": "admin9531@gmail.com", "password": "…", "remember_me": true, "device_id": "<64 hex>"}
```
`200`:
```json
{
  "access_token": "<JWT>", "token_type": "bearer", "expires_in": 1800,
  "refresh_token": "<opaque>", "refresh_expires_at": "2026-12-01T12:00:00Z",
  "device_secret": "<64 hex>",
  "user": {"id": 1, "organization_id": 1, "email": "…", "full_name": "Owner", "role": "owner",
           "team_id": null, "must_change_password": false, "permissions": ["members.add", "…"],
           "last_login_at": "…"}
}
```

**Device binding:** the first successful sign-in binds the account to `device_id`. Every sign-in returns a new `device_secret`, and the previous one stops working. If `must_change_password` is `true`, the client must show the password change screen before anything else.

| Status | When |
|---|---|
| 401 | `Invalid email or password.` The same answer for unknown emails. |
| 403 | The account is disabled, or it's bound to another computer. The device is only checked after the password is verified. |
| 429 | Locked after 5 failures. The message says how many minutes are left. |
| 422 | The email is malformed, or a field is missing. |

### `POST /api/auth/refresh`
`{"refresh_token": "…"}` with a device signature (no bearer token) → `200` with the same body as login, but with `device_secret: null`. The body includes a **new** refresh token. Store it; the old one is now invalid.

`401` means expired, revoked or unknown. Reusing a rotated-out token also revokes all of the user's sessions.

### `POST /api/auth/logout`
`{"refresh_token": "…"}` → `200 {"message": "Signed out."}`. This always succeeds. It needs no signature, so a session can always be revoked.

### `GET /api/auth/me` 🔒
`200` returns the user object. `401` means the token is missing, invalid or expired, the password changed after the token was issued, or the device signature failed.

### `POST /api/auth/change-password` 🔒
`{"current_password": "…", "new_password": "…", "remember_me": false}` → `200` with the same body as refresh. Every other session is revoked, and access tokens issued earlier stop working.

This endpoint is allowed while `must_change_password` is set, and changing the password clears it.

| Status | When |
|---|---|
| 400 | The current password is wrong. |
| 422 | The password policy failed, or the new password is the same as the current one. |

### `POST /api/auth/forgot-password`
`{"email": "…"}` → `200 {"message": "If an account exists for that email, a reset code has been sent."}`. The response is identical whether or not the account exists.

The code is 6 digits, valid for 15 minutes, and allows 5 attempts. Requests for the same account are throttled to one per 60 seconds.

### `POST /api/auth/reset-password`
`{"email": "…", "code": "123456", "new_password": "…"}` → `200`.

| Status | When |
|---|---|
| 422 | The password policy failed. The new password needs 8–128 characters and at least three of: lowercase, uppercase, digits, symbols. |
| 400 | The code is invalid or expired. |

On success, all of the user's sessions are revoked, and `must_change_password` is cleared.

## Teams and members

See [permissions.md](permissions.md) for who can do what.

### `GET /api/teams` 🔒
`200 [{"id": 1, "name": "Sales", "member_count": 3, "leaders": [{"id": 4, "name": "Lena"}]}]`. `member_count` counts plain members only. Holders of the Owner role, `teams.create` or `teams.rename` get every team; anyone else gets only their own team.

### `POST /api/teams` 🔒 `teams.create`
`{"name": "Sales"}` → `201` with the team. Returns `409` if the organization already has a team with that name (case-insensitive).

### `PATCH /api/teams/{id}` 🔒 `teams.rename`
`{"name": "Sales EMEA"}` → `200` with the team. Returns `404` for an unknown team, or `409` if the name is taken.

### `POST /api/teams/{id}/leaders` 🔒 Owner
`{"user_id": 5}` → `200` with the member.

- **A plain member** becomes a Team Leader of this team and leaves their own team.
- **A Team Leader** leads this team in addition to their others.
- **Errors:** `422` for the Owner as target, `404` for an unknown team or person.

### `DELETE /api/teams/{id}/leaders/{user_id}` 🔒 Owner
`200` with the member: they no longer lead this team. If it was their last team, they become a plain member with no team. Returns `404` if they don't lead it.

### `DELETE /api/teams/{id}` 🔒 Owner
`200 {"message": "Team deleted. 2 members now have no team."}`

- **Members:** they keep their accounts, with `team_id: null`, until the Owner assigns a new team with `PATCH /api/members/{id}`.
- **Team Leaders:** the team's leaders stop leading it. Those who lead no other team become regular members (`role: "member"`) and lose Team Leader permissions on their next request. Their role bundles are kept.
- **Errors:** `403` for anyone but the Owner, `404` for an unknown team.

### `GET /api/members` 🔒 `members.view`
`200` returns a list of members.
- **The Owner** gets everyone.
- **Anyone else** gets their own team, plus, with `members.team`, members who have no team, so they can be brought in.

Each member looks like this:
```json
{"id": 5, "email": "…", "full_name": "…", "role": "member", "team_id": 1, "team_name": "Sales",
 "is_active": true, "must_change_password": true, "device_registered": false, "last_login_at": null,
 "role_bundles": [{"id": 2, "name": "Onboarding"}], "permissions": ["members.add", "members.view", "projects.view"]}
```

### `POST /api/members` 🔒 `members.add`
`{"email": "…", "full_name": "…", "team_id": 1, "role": "member" | "team_leader", "initial_password": "…", "role_bundle_ids": [2]}` → `201` with the member.

- **Optional fields:** `role_bundle_ids` and `team_id`.
- **The Owner** may leave out `team_id` (or send `null`) to add someone with no team. A Team Leader still needs a team (`422`).
- **Everyone else** adds to one of their teams. An omitted `team_id` works only when they have exactly one team; otherwise it's `422 Select a team.`

The new account must change its password at first sign-in.

| Status | When |
|---|---|
| 403 | A non-owner tried to add to another team, to add a Team Leader, or to give a bundle they may not hand out. |
| 404 | The team or a role bundle doesn't exist in the organization. |
| 409 | The email is already registered. |
| 422 | The initial password fails the password policy, or a field is missing. |

### `PATCH /api/members/{id}` 🔒 `members.view`
```json
{"full_name": "…", "email": "…", "team_id": 2, "is_active": false, "new_password": "…",
 "role": "member" | "team_leader", "role_bundle_ids": [1, 2]}
```
→ `200` with the member.

- **All fields are optional;** an omitted field is left unchanged.
- **`team_id`** is applied whenever it's sent, so `"team_id": null` takes the member out of their team.
  - The Owner can move anyone anywhere.
  - Holders of `members.team` (Team Leaders by default) can only bring a plain member with no team into their own team, or take a plain member of their own team out of it.
  - A Team Leader must always have a team (`422 A Team Leader must belong to a team.`, and nothing is saved). To clear a leader's team, also send `"role": "member"`.
- **`role_bundle_ids`** replaces the member's whole set.
- **`new_password`** sets a new initial password that the member must change at their next sign-in.
- **Sign-out:** changing `email`, setting `new_password` or setting `is_active: false` revokes the member's sessions. An email change also invalidates their device signatures, because the email is part of every signature.

| Status | When |
|---|---|
| 403 | The caller lacks the permission for the change: `members.edit` for details, the Owner or `members.team` (within the limits above) for `team_id`, the Owner for `role`, or `members.assign_roles` plus every permission in each bundle added or removed. Also returned for a target outside a non-owner's own team's plain members, or for bundle changes on the Owner. |
| 404 | The member, team or a role bundle doesn't exist. |
| 409 | The new email is already registered. |
| 422 | `new_password` fails the policy; someone tried to disable themselves, set their own password, or put the Owner in a team; or a Team Leader would be left without a team. |

### `DELETE /api/members/{id}` 🔒 `members.delete`
`200 {"message": "Member deleted."}`. The account is deleted along with its device binding, sessions and role bundle assignments. The audit log records the deleted email and name.

| Status | When |
|---|---|
| 403 | The target is outside a non-owner's own team's plain members. |
| 404 | The member doesn't exist. |
| 422 | The target is the Owner. |

### `POST /api/members/{id}/reset-device` 🔒 `members.reset_device`
`200` with the member. The member's computer is unbound and their sessions end; their next sign-in binds the computer it's made from.

- **Who can reset:** the Owner can reset anyone in the organization. Anyone else with the permission can reset only plain members of their own team.

## Role bundles

### `GET /api/role-bundles` 🔒 `members.view`
`200 [{"id": 2, "name": "Onboarding", "description": "…", "permissions": ["members.add"], "member_count": 1}]`

### `POST /api/role-bundles` 🔒 Owner
`{"name": "Onboarding", "description": "…", "permissions": ["members.add", "members.reset_device"]}` → `201`. Permissions must come from `shared/permissions.py`, with at least one. Returns `409` if the name is taken.

### `PUT /api/role-bundles/{id}` 🔒 Owner
Same body as create → `200`. The change applies at once to every member holding the bundle.

### `DELETE /api/role-bundles/{id}` 🔒 Owner
`200`. The bundle is removed from everyone who holds it.
- **The Owner's own device:** `python -m server.manage reset-device <email>` on the server.
