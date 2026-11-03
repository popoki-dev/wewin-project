"""API contract shared by server and client: paths and policy constants (stdlib only).

Request/response shapes are defined by the server's Pydantic schemas and
documented in docs/api.md; this module holds the values both sides must agree on.
"""

from __future__ import annotations

API_PREFIX = "/api"
APP_ID = "WeWin"


class Paths:
    HEALTH = f"{API_PREFIX}/health"

    AUTH_LOGIN = f"{API_PREFIX}/auth/login"
    AUTH_REFRESH = f"{API_PREFIX}/auth/refresh"
    AUTH_LOGOUT = f"{API_PREFIX}/auth/logout"
    AUTH_ME = f"{API_PREFIX}/auth/me"
    AUTH_FORGOT_PASSWORD = f"{API_PREFIX}/auth/forgot-password"
    AUTH_RESET_PASSWORD = f"{API_PREFIX}/auth/reset-password"
    AUTH_CHANGE_PASSWORD = f"{API_PREFIX}/auth/change-password"

    TEAMS = f"{API_PREFIX}/teams"
    MEMBERS = f"{API_PREFIX}/members"
    ROLE_BUNDLES = f"{API_PREFIX}/role-bundles"
    PROJECTS = f"{API_PREFIX}/projects"

    @staticmethod
    def project(project_id: int) -> str:
        return f"{API_PREFIX}/projects/{project_id}"

    @staticmethod
    def project_check(project_id: int) -> str:
        return f"{API_PREFIX}/projects/{project_id}/check"

    @staticmethod
    def team(team_id: int) -> str:
        return f"{API_PREFIX}/teams/{team_id}"

    @staticmethod
    def team_leaders(team_id: int) -> str:
        return f"{API_PREFIX}/teams/{team_id}/leaders"

    @staticmethod
    def team_leader(team_id: int, user_id: int) -> str:
        return f"{API_PREFIX}/teams/{team_id}/leaders/{user_id}"

    @staticmethod
    def member(user_id: int) -> str:
        return f"{API_PREFIX}/members/{user_id}"

    @staticmethod
    def role_bundle(bundle_id: int) -> str:
        return f"{API_PREFIX}/role-bundles/{bundle_id}"

    @staticmethod
    def member_device_reset(user_id: int) -> str:
        return f"{API_PREFIX}/members/{user_id}/reset-device"


# Password policy (validated by the server, hinted by the client).
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_MIN_CHARACTER_CLASSES = 3

RESET_CODE_LENGTH = 6
