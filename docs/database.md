# Database

PostgreSQL 16, accessed through SQLAlchemy 2.0 with the psycopg 3 driver. Alembic manages the schema.

## Tables (migrations `0001`–`0004`)

| Table | Purpose | Key columns |
|---|---|---|
| `organizations` | Tenant. Every user belongs to one. | `name` |
| `teams` | Groups of members | `organization_id`, `name` (unique per organization) |
| `users` | Accounts | `organization_id` → organizations, `team_id` → teams (`SET NULL`; none for the Owner), `email` (unique), `password_hash` (Argon2id), `role` (`owner`/`team_leader`/`member`), `is_active`, `must_change_password`, lockout fields (`failed_login_count`, `locked_until`), `password_changed_at` |
| `team_leaders` | Which teams each Team Leader leads (one or more) | `team_id`, `user_id` (both `CASCADE`). Team Leaders have no `users.team_id`; plain members belong to at most one team through `users.team_id`. |
| `role_bundles` | Named permission sets defined by the Owner | `organization_id`, `name` (unique per organization), `description`, `permissions` (JSON list of `shared/permissions.py` values) |
| `user_role_bundles` | Which bundles each user holds | `user_id`, `bundle_id` (both `CASCADE`) |
| `devices` | The one computer each account is bound to | `user_id` (unique), `device_id` (SHA-256 of the MAC), `secret_nonce`, `last_seen_at`. The device secret is derived from `WEWIN_SECRET_KEY` and `secret_nonce`, and it's never stored. |
| `device_request_nonces` | Replay protection for signed requests | `device_pk`, `nonce` (unique per device). Rows are kept for 10 minutes. |
| `refresh_sessions` | Signed-in sessions | `user_id`, `token_hash` (SHA-256, unique), `remember_me`, `expires_at`, `revoked_at`, `ip_address`, `user_agent` |
| `password_reset_codes` | One-time reset codes | `user_id`, `code_hash` (HMAC-SHA256), `attempts`, `expires_at`, `used_at` |
| `audit_logs` | Append-only event log | `organization_id`, `user_id` (both `SET NULL` on delete), `action`, `ip_address`, `user_agent`, `details` (JSONB), `created_at` |

Conventions:

- **Timestamps** are `TIMESTAMPTZ` in UTC.
- **Enums** are stored as `VARCHAR` (`native_enum=False`), so adding a role is a code change rather than an `ALTER TYPE`.
- **Constraint names** follow a fixed naming convention (`pk_`, `fk_`, `uq_`, `ix_`), set in `models/base.py`.
- **Emails** are stored lower-case and are unique across organizations, because sign-in is by email alone.

Planned with their modules (not created yet): `projects`, `project_members` and `revenue`. Each will carry `organization_id`.

- **`0002`** renamed the `admin` role to `team_leader`.
- **`0004`** moved each Team Leader's `team_id` into `team_leaders`, so leaders can lead several teams.

Changing `WEWIN_SECRET_KEY` invalidates every device secret. Users then need to sign in with their password again, on the same computer.

## Working with migrations

Run from `server/`, with `WEWIN_DATABASE_URL` pointing at the target database:

```bash
alembic revision --autogenerate -m "add projects"   # after changing models; review the file!
alembic upgrade head
alembic downgrade -1
alembic check                                       # fails if models and migrations differ
```

`env.py` renders the app's custom column types as plain SQLAlchemy types, so migration files never import application code.

## Backups

The `backup` service in `deployment/docker-compose.yml` runs `pg_dump --format=custom` at start-up and then every 24 hours. Dumps go to `deployment/backups/` (set `BACKUP_DIR`) and are kept for 14 days (`BACKUP_KEEP_DAYS`).

- **Restore:** `cd deployment && ./backup/restore.sh backups/wewin-<timestamp>.dump`.
- **Copy dumps off the VPS** (rsync, object storage); a backup on the same disk doesn't survive losing the disk.
