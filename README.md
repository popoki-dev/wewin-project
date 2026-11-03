# WeWin

Manage organization members, projects and revenue.

| Component | Technology |
|---|---|
| Desktop application | PySide6 + QML (MVVM) |
| Client ↔ server | HTTPS REST API (JSON) |
| Backend | FastAPI, Pydantic, SQLAlchemy 2.0, Alembic |
| Database | PostgreSQL 16 |
| Authentication | Access/refresh tokens; passwords hashed with Argon2id |
| Reverse proxy | Caddy (automatic Let's Encrypt HTTPS) |
| Deployment | Docker Compose on Ubuntu LTS |

**Current milestone:** device-bound sign-in with signed requests, Remember Me, Forgot Password, teams and members (added by the Owner or a Team Leader, with a forced password change at first login), projects with payment history and Leader/Owner checks, light/dark themes and audit logging. Revenue comes next.

See [docs/architecture.md](docs/architecture.md), [docs/api.md](docs/api.md), [docs/database.md](docs/database.md) and [docs/permissions.md](docs/permissions.md).

## Local development

Run everything from the repository root.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

# PostgreSQL in Docker on 127.0.0.1:5433 (the server's default database URL)
docker compose -f deployment/docker-compose.dev.yml up -d

# API: applies migrations, creates the owner, serves http://127.0.0.1:8000
python -m server.main

# Desktop client (another terminal)
python -m client.main
```

Sign in with server `localhost:8000`, email `admin9531@gmail.com` and password `asdqwe!@#123`.

The first sign-in binds each account to the computer it's made from; other computers are refused. To try a second computer on one machine, start the client with `WEWIN_DEVICE_MAC=02:00:00:00:00:01` (testing only). To release a binding, use **Reset device** on the Members page, or run `python -m server.manage reset-device <email>` for the Owner.

The client assumes **https://** for any host you type without a scheme. Plain http is used automatically only for `localhost`/`127.0.0.1`, and the login screen warns if you type `http://` for a remote server.

Without SMTP configured, password-reset codes are printed in the server log.

### Tests

```bash
WEWIN_TEST_DATABASE_URL=postgresql+psycopg://wewin:wewin@127.0.0.1:5433/wewin_test \
QT_QPA_PLATFORM=offscreen python -m pytest
```

Create the test database once with `docker compose -f deployment/docker-compose.dev.yml exec db createdb -U wewin wewin_test`. Without `WEWIN_TEST_DATABASE_URL`, the server tests fall back to SQLite. Either way, the schema is built by the Alembic migrations.

## Deploying to a VPS (Ubuntu LTS)

1. Point a DNS record (e.g. `wewin.example.com`) at the VPS.
2. Install Docker Engine with the Compose plugin, then open the firewall: `ufw allow OpenSSH && ufw allow 80,443/tcp && ufw allow 443/udp && ufw enable`.
3. Copy this repository to the server.
4. Configure and start the stack:
   ```bash
   cd deployment
   cp .env.example .env    # set WEWIN_DOMAIN, POSTGRES_PASSWORD, WEWIN_SECRET_KEY,
                           # WEWIN_OWNER_PASSWORD, SMTP settings
   docker compose up -d --build
   docker compose ps       # all services should be "healthy"
   ```
5. In the desktop client, use server `wewin.example.com`.

What the stack does:

- **db** is PostgreSQL. It sits on an internal network and isn't reachable from the internet.
- **server** runs migrations and creates the owner on start, then serves on the internal network only.
- **caddy** terminates TLS, redirects HTTP to HTTPS, adds security headers and proxies to the server.
- **backup** writes a daily `pg_dump` to `deployment/backups/`, keeping 14 days. Copy these off the machine. To restore: `./backup/restore.sh backups/<file>.dump`.

To update, run `docker compose up -d --build` again. Migrations apply automatically.

## Configuration

The server reads `WEWIN_*` environment variables, or `deployment/.env` in Docker; see `server/app/core/config.py`.

| Variable | Default | Notes |
|---|---|---|
| `WEWIN_ENVIRONMENT` | `development` | `production` requires `WEWIN_SECRET_KEY` and disables `/docs` |
| `WEWIN_DATABASE_URL` | `postgresql+psycopg://wewin:wewin@127.0.0.1:5433/wewin` | Set by Compose in production |
| `WEWIN_SECRET_KEY` | temporary key (dev only) | 32+ characters; signs tokens and reset codes |
| `WEWIN_OWNER_EMAIL` / `_PASSWORD` / `_NAME`, `WEWIN_ORGANIZATION_NAME` | see `.env.example` | Used only when no owner exists yet. The password must meet the password policy, and production rejects the development default |
| `WEWIN_ACCESS_TOKEN_MINUTES` | 30 | |
| `WEWIN_REFRESH_TOKEN_HOURS` | 12 | Session length without Remember Me |
| `WEWIN_REMEMBER_ME_DAYS` | 30 | Session length with Remember Me |
| `WEWIN_MAX_FAILED_LOGINS` / `WEWIN_LOCKOUT_MINUTES` | 5 / 15 | |
| `WEWIN_SMTP_*` | unset | Delivers reset codes by email |
| `WEWIN_WORKERS` | 2 | Uvicorn workers in Docker |

## Layout

```
client/      main.py · app/ (bootstrap, storage) · api/ · viewmodels/ · frontend/qml/
server/      main.py · manage.py · alembic.ini · app/{core,database,models,schemas,repositories,services,api}
shared/      enums.py · api_contracts.py
deployment/  Dockerfile · docker-compose.yml · docker-compose.dev.yml · caddy/ · backup/
tests/       client/ · server/
docs/        architecture · database · api · permissions
```
