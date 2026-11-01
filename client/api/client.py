"""Asynchronous JSON-over-HTTPS client built on QNetworkAccessManager."""

from __future__ import annotations

import ipaddress
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QByteArray, QObject, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from client import __version__

REQUEST_TIMEOUT_MS = 15_000
_REQUEST_ID = "wewinRequestId"


@dataclass
class ApiResult:
    ok: bool
    status: int  # 0 when no HTTP response was received
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


Callback = Callable[[ApiResult], None]
# (method, path) -> device signature headers for that request
Signer = Callable[[str, str], dict[str, str]]


def is_loopback_host(host: str) -> bool:
    host = host.strip("[]").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def normalize_server_url(raw: str) -> str:
    """Turn user input into a base URL.

    'wewin.example.com' -> 'https://wewin.example.com' (HTTPS by default);
    'localhost:8000'    -> 'http://localhost:8000'     (local development).
    Returns '' when the input is not a usable http(s) URL.
    """
    url = raw.strip()
    if not url:
        return ""
    if "://" not in url:
        host = QUrl("//" + url).host()
        url = ("http://" if is_loopback_host(host) else "https://") + url
    url = url.rstrip("/")
    parsed = QUrl(url)
    if not parsed.isValid() or not parsed.host() or parsed.scheme() not in ("http", "https"):
        return ""
    return url


def is_insecure_remote(url: str) -> bool:
    """True for plain-HTTP URLs that leave this machine."""
    parsed = QUrl(url)
    return parsed.scheme() == "http" and not is_loopback_host(parsed.host())


class ApiClient(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._nam.setTransferTimeout(REQUEST_TIMEOUT_MS)
        self._nam.finished.connect(self._finished)
        # In-flight requests by id. Keeping callbacks here (not in per-reply
        # lambdas) keeps them alive until the reply arrives.
        self._pending: dict[int, tuple[str, Callback]] = {}
        self._next_id = 0
        self._signer: Signer | None = None

    def set_signer(self, signer: Signer | None) -> None:
        """Sign every request with the device secret while signed in; None stops signing."""
        self._signer = signer

    def get(self, server: str, path: str, callback: Callback, token: str | None = None) -> None:
        self._send("GET", server, path, None, callback, token)

    def post(self, server: str, path: str, body: dict, callback: Callback, token: str | None = None) -> None:
        self._send("POST", server, path, body, callback, token)

    def put(self, server: str, path: str, body: dict, callback: Callback, token: str | None = None) -> None:
        self._send("PUT", server, path, body, callback, token)

    def patch(self, server: str, path: str, body: dict, callback: Callback, token: str | None = None) -> None:
        self._send("PATCH", server, path, body, callback, token)

    def delete(self, server: str, path: str, callback: Callback, token: str | None = None) -> None:
        self._send("DELETE", server, path, None, callback, token)

    def _send(self, method: str, server: str, path: str, body: dict | None, callback: Callback, token: str | None) -> None:
        url = QUrl(server + path)
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setRawHeader(b"Accept", b"application/json")
        request.setRawHeader(b"User-Agent", f"WeWin-Desktop/{__version__}".encode())
        if token:
            request.setRawHeader(b"Authorization", f"Bearer {token}".encode())
        if self._signer is not None:
            # Sign the full URL path, which includes any prefix in the server address.
            for name, value in self._signer(method, url.path()).items():
                request.setRawHeader(name.encode(), value.encode())

        data = QByteArray(json.dumps(body or {}).encode())
        if method == "GET":
            reply = self._nam.get(request)
        elif method == "POST":
            reply = self._nam.post(request, data)
        elif method == "PUT":
            reply = self._nam.put(request, data)
        elif method == "DELETE":
            reply = self._nam.deleteResource(request)
        else:
            reply = self._nam.sendCustomRequest(request, method.encode(), data)

        self._next_id += 1
        reply.setProperty(_REQUEST_ID, self._next_id)
        self._pending[self._next_id] = (server, callback)

    def _finished(self, reply: QNetworkReply) -> None:
        entry = self._pending.pop(reply.property(_REQUEST_ID), None)
        reply.deleteLater()
        if entry is None:
            return
        server, callback = entry
        callback(self._to_result(reply, server))

    @staticmethod
    def _to_result(reply: QNetworkReply, server: str) -> ApiResult:
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) or 0
        raw = bytes(reply.readAll().data())

        if status == 0:
            error = reply.error()
            errors = QNetworkReply.NetworkError
            if error == errors.SslHandshakeFailedError:
                message = f"Secure connection to {server} failed: the server's certificate is not trusted."
            elif error == errors.OperationCanceledError:
                message = f"The server at {server} took too long to respond."
            elif error == errors.HostNotFoundError:
                message = f"Server not found: {QUrl(server).host()}."
            else:
                message = f"Could not reach the server at {server}."
            return ApiResult(False, 0, {}, message)

        try:
            data = json.loads(raw) if raw else {}
            if isinstance(data, list):  # list endpoints
                data = {"items": data}
            if not isinstance(data, dict):
                raise ValueError
        except ValueError:
            return ApiResult(False, status, {}, "Unexpected response. Is this a WeWin server?")

        if 200 <= status < 300:
            return ApiResult(True, status, data)
        detail = data.get("detail")
        message = detail if isinstance(detail, str) else f"Request failed (HTTP {status})."
        return ApiResult(False, status, data, message)
