"""Sign-in helpers for server tests: they act like a desktop client on one PC."""

from __future__ import annotations

from shared.api_contracts import Paths
from shared.device_signature import device_id_from_mac, signed_headers

OWNER_EMAIL = "admin9531@gmail.com"
OWNER_PASSWORD = "asdqwe!@#123"

PC_A = device_id_from_mac("02:00:00:00:00:0A")
PC_B = device_id_from_mac("02:00:00:00:00:0B")


def login(client, email=OWNER_EMAIL, password=OWNER_PASSWORD, remember_me=False, device_id=PC_A):
    body = {"email": email, "password": password, "remember_me": remember_me, "device_id": device_id}
    return client.post(Paths.AUTH_LOGIN, json=body)


class DeviceSession:
    """A signed-in client: bearer token plus a fresh device signature on every request."""

    def __init__(self, client, tokens: dict, device_id: str = PC_A, device_secret: str | None = None) -> None:
        self.client = client
        self.device_id = device_id
        self.device_secret = device_secret or tokens["device_secret"]
        self.update(tokens)

    def update(self, tokens: dict) -> None:
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens["refresh_token"]
        self.email = tokens["user"]["email"]
        self.user = tokens["user"]

    def headers(self, method: str, path: str, *, bearer: bool = True) -> dict[str, str]:
        headers = signed_headers(self.device_secret, self.device_id, self.email, method, path)
        if bearer:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def get(self, path: str):
        return self.client.get(path, headers=self.headers("GET", path))

    def post(self, path: str, json: dict | None = None):
        return self.client.post(path, json=json or {}, headers=self.headers("POST", path))

    def refresh(self, refresh_token: str | None = None):
        body = {"refresh_token": refresh_token or self.refresh_token}
        r = self.client.post(Paths.AUTH_REFRESH, json=body, headers=self.headers("POST", Paths.AUTH_REFRESH, bearer=False))
        if r.status_code == 200:
            self.update(r.json())
        return r


def sign_in(client, email=OWNER_EMAIL, password=OWNER_PASSWORD, *, device_id=PC_A, remember_me=False) -> DeviceSession:
    r = login(client, email, password, remember_me, device_id)
    assert r.status_code == 200, r.text
    return DeviceSession(client, r.json(), device_id)
