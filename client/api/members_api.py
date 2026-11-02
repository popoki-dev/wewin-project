from __future__ import annotations

from shared.api_contracts import Paths

from .client import ApiClient, Callback


class MembersApi:
    """Typed wrapper over the /api/teams and /api/members endpoints."""

    def __init__(self, client: ApiClient) -> None:
        self._client = client

    def list_teams(self, server: str, token: str, callback: Callback) -> None:
        self._client.get(server, Paths.TEAMS, callback, token)

    def create_team(self, server: str, token: str, name: str, callback: Callback) -> None:
        self._client.post(server, Paths.TEAMS, {"name": name}, callback, token)

    def rename_team(self, server: str, token: str, team_id: int, name: str, callback: Callback) -> None:
        self._client.patch(server, Paths.team(team_id), {"name": name}, callback, token)

    def delete_team(self, server: str, token: str, team_id: int, callback: Callback) -> None:
        self._client.delete(server, Paths.team(team_id), callback, token)

    def add_team_leader(self, server: str, token: str, team_id: int, user_id: int, callback: Callback) -> None:
        self._client.post(server, Paths.team_leaders(team_id), {"user_id": user_id}, callback, token)

    def remove_team_leader(self, server: str, token: str, team_id: int, user_id: int, callback: Callback) -> None:
        self._client.delete(server, Paths.team_leader(team_id, user_id), callback, token)

    def list_members(self, server: str, token: str, callback: Callback) -> None:
        self._client.get(server, Paths.MEMBERS, callback, token)

    def add_member(self, server: str, token: str, body: dict, callback: Callback) -> None:
        self._client.post(server, Paths.MEMBERS, body, callback, token)

    def update_member(self, server: str, token: str, user_id: int, body: dict, callback: Callback) -> None:
        self._client.patch(server, Paths.member(user_id), body, callback, token)

    def delete_member(self, server: str, token: str, user_id: int, callback: Callback) -> None:
        self._client.delete(server, Paths.member(user_id), callback, token)

    def reset_device(self, server: str, token: str, user_id: int, callback: Callback) -> None:
        self._client.post(server, Paths.member_device_reset(user_id), {}, callback, token)

    def list_bundles(self, server: str, token: str, callback: Callback) -> None:
        self._client.get(server, Paths.ROLE_BUNDLES, callback, token)

    def create_bundle(self, server: str, token: str, body: dict, callback: Callback) -> None:
        self._client.post(server, Paths.ROLE_BUNDLES, body, callback, token)

    def update_bundle(self, server: str, token: str, bundle_id: int, body: dict, callback: Callback) -> None:
        self._client.put(server, Paths.role_bundle(bundle_id), body, callback, token)

    def delete_bundle(self, server: str, token: str, bundle_id: int, callback: Callback) -> None:
        self._client.delete(server, Paths.role_bundle(bundle_id), callback, token)
