# Architecture

WeWin is a desktop client talking to a central API server over HTTPS.

```
 Desktop (PySide6 + QML)                    VPS (Ubuntu LTS, Docker Compose)
┌───────────────────────────┐            ┌──────────────────────────────────────────┐
│ QML pages / components    │            │ Caddy ── TLS (Let's Encrypt), :80 → :443 │
│        ▲ properties/slots │   HTTPS    │   │                                      │
│ ViewModels (QObject)      │  REST/JSON │   ▼  reverse proxy (internal network)    │
│        ▲ callbacks        │ ─────────► │ FastAPI (uvicorn workers)                │
│ API layer (QNetwork…)     │            │   routes → services → repositories       │
└───────────────────────────┘            │   │                                      │
                                         │   ▼ SQLAlchemy 2.0 / psycopg 3           │
                                         │ PostgreSQL 16  ◄── nightly pg_dump       │
                                         └──────────────────────────────────────────┘
```

## Repository layout

| Path | Role |
|---|---|
| `client/` | Desktop application. Ships to users. |
| `server/` | API server. Ships as a Docker image. |
| `shared/` | Stdlib-only code both sides import: enums and API contract constants. |
| `deployment/` | Dockerfile, Compose stacks, Caddy config, backup scripts. |
| `tests/` | `tests/server` (API, against PostgreSQL or SQLite) and `tests/client` (view models, URL handling). |

All imports are absolute from the repository root (`server.app…`, `client.api…`, `shared…`). Run commands from the root.

## Server layers

Each layer only calls the one below it:

1. **`api/routes/`**: HTTP only. Parse the request (Pydantic schemas), call a service, shape the response. No SQL.
2. **`services/`**: use cases and business rules (lockout, token rotation, reset codes). These own the transaction: they `commit()`. They raise `AuthError` (or future domain errors), which `main.py` maps to HTTP responses.
3. **`repositories/`**: queries and persistence for one aggregate. No business rules, no commits.
4. **`models/`**: SQLAlchemy ORM tables.

`core/` holds cross-cutting concerns:

- `config.py`: settings from the `WEWIN_*` environment variables.
- `security.py`: Argon2id, JWT and the password policy.
- `authentication.py`: the current user and client info.
- `permissions.py`: role checks.

Schema changes go through **Alembic** (`server/app/database/migrations`). In Docker, the entrypoint runs `python -m server.manage init`, which migrates and then seeds the owner, before uvicorn starts.

## Client layers (MVVM)

1. **QML (`frontend/qml`)**: presentation only.
   - `themes/Theme.qml`: a singleton of light/dark design tokens.
   - `components/`: reusable controls.
   - `layouts/`: page frames. `AuthLayout` is the signed-out split screen; `AppShell` is the signed-in sidebar.
   - `pages/`: screens.
2. **ViewModels (`viewmodels/`)**: `QObject`s with Qt properties, signals and slots. They're registered as QML singletons under `WeWin.ViewModels`, and they validate input and hold UI state.
3. **API (`api/`)**: `client.py` is an async `QNetworkAccessManager` wrapper that never blocks the UI thread. `*_api.py` holds one typed wrapper per resource.
4. **`app/`**: `bootstrap.py` wires everything together; `storage.py` holds preferences and the Remember Me token.

## Authentication flow

1. `POST /api/auth/login` sends the computer's **device ID** (SHA-256 of its MAC address, from `client/app/device.py`). The first sign-in binds the account to that computer, and other computers are refused until the binding is reset. The response carries a fresh **device secret**, a 30-minute JWT **access token** and an opaque **refresh token**. The refresh token lasts 12 hours, or 30 days with Remember Me, and is stored server-side as a SHA-256 hash.
2. The client renews the access token shortly before it expires with `POST /api/auth/refresh`. Every refresh **rotates** the refresh token; presenting a rotated-out token revokes all of that user's sessions, because it is treated as a theft signal.
3. With Remember Me, the refresh token is kept in the OS keyring, and the next launch signs in silently. The password is never stored.
4. Every later request is **signed**: an HMAC-SHA256 over the device ID, email, UTC timestamp, a nonce, the method and the path, keyed by the device secret. `ApiClient` adds the headers; `get_signed_in_user` verifies them and rejects stale timestamps and replays. The secret is never stored on the server; it's derived from `WEWIN_SECRET_KEY`.
5. An account created with an initial password has `must_change_password` set. The client opens the change-password screen, and the server refuses everything else until the password is changed.
6. A password change or reset revokes every session. It also invalidates outstanding access tokens, which carry a `pwv` claim tied to `password_changed_at`.
7. With Remember Me, the device secret is kept in the keyring with the refresh token, so the next launch can sign the silent refresh.

## Deliberately not included (yet)

There's no Redis, Celery, Kubernetes or microservices. Background work like sending mail runs in-process (FastAPI background tasks). Revisit this when a workload needs it.
