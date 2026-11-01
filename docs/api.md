# API

Base path `/api`. JSON in and out. Path constants live in `shared/api_contracts.py`.

**Errors** always have the shape `{"detail": "<human-readable message>"}`, including validation errors (422). The client shows `detail` as-is.

**Authentication:** send `Authorization: Bearer <access_token>` to protected endpoints.

In development, interactive docs are at `/docs`; they're disabled in production.

## Meta

### `GET /api/health`
`200 {"status": "ok", "app": "WeWin", "version": "0.2.0", "database": "ok" | "unavailable"}`

The client uses `app == "WeWin"` to confirm the server address points at a WeWin server.

## Auth

### `POST /api/auth/login`
```json
{"email": "admin9531@gmail.com", "password": "…", "remember_me": true}
```
`200`:
```json
{
  "access_token": "<JWT>", "token_type": "bearer", "expires_in": 1800,
  "refresh_token": "<opaque>", "refresh_expires_at": "2026-12-01T12:00:00Z",
  "user": {"id": 1, "organization_id": 1, "email": "…", "full_name": "Owner", "role": "owner", "last_login_at": "…"}
}
```
| Status | When |
|---|---|
| 401 | `Invalid email or password.` The same answer for unknown emails. |
| 403 | The account is disabled. |
| 429 | Locked after 5 failures. The message says how many minutes are left. |
| 422 | The email is malformed, or a field is missing. |

### `POST /api/auth/refresh`
`{"refresh_token": "…"}` → `200` with the same body as login, including a **new** refresh token. Store it; the old one is now invalid.

`401` means expired, revoked or unknown. Reusing a rotated-out token also revokes all of the user's sessions.

### `POST /api/auth/logout`
`{"refresh_token": "…"}` → `200 {"message": "Signed out."}`. This always succeeds.

### `GET /api/auth/me` 🔒
`200` returns the user object. `401` means the token is missing, invalid or expired, or the password changed after the token was issued.

### `POST /api/auth/forgot-password`
`{"email": "…"}` → `200 {"message": "If an account exists for that email, a reset code has been sent."}`. The response is identical whether or not the account exists.

The code is 6 digits, valid for 15 minutes, and allows 5 attempts. Requests for the same account are throttled to one per 60 seconds.

### `POST /api/auth/reset-password`
`{"email": "…", "code": "123456", "new_password": "…"}` → `200`.

| Status | When |
|---|---|
| 422 | The password policy failed. The new password needs 8–128 characters and at least three of: lowercase, uppercase, digits, symbols. |
| 400 | The code is invalid or expired. |

On success, all of the user's sessions are revoked.
