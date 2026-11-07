from __future__ import annotations

from shared.api_contracts import Paths

from .client import ApiClient, Callback


class ProjectsApi:
    """Typed wrapper over the /api/projects endpoints."""

    def __init__(self, client: ApiClient) -> None:
        self._client = client

    def list(self, server: str, token: str, callback: Callback) -> None:
        self._client.get(server, Paths.PROJECTS, callback, token)

    def project_owner_options(self, server: str, token: str, callback: Callback) -> None:
        self._client.get(server, Paths.PROJECT_OWNER_OPTIONS, callback, token)

    def create(self, server: str, token: str, body: dict, callback: Callback) -> None:
        self._client.post(server, Paths.PROJECTS, body, callback, token)

    def update(self, server: str, token: str, project_id: int, body: dict, callback: Callback) -> None:
        self._client.put(server, Paths.project(project_id), body, callback, token)

    def delete(self, server: str, token: str, project_id: int, callback: Callback) -> None:
        self._client.delete(server, Paths.project(project_id), callback, token)

    def check(self, server: str, token: str, project_id: int, callback: Callback) -> None:
        self._client.post(server, Paths.project_check(project_id), {}, callback, token)

    def uncheck(self, server: str, token: str, project_id: int, level: str, callback: Callback) -> None:
        # The query string is not part of the signed path (both sides sign the path only).
        self._client.delete(server, f"{Paths.project_check(project_id)}?level={level}", callback, token)
