import pytest

from client.api.client import is_insecure_remote, normalize_server_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("wewin.example.com", "https://wewin.example.com"),  # HTTPS by default
        ("wewin.example.com:8443/", "https://wewin.example.com:8443"),
        ("localhost:8000", "http://localhost:8000"),  # local development
        ("127.0.0.1:8000", "http://127.0.0.1:8000"),
        ("  https://wewin.example.com/ ", "https://wewin.example.com"),
        ("http://10.0.0.5:8000/api/", "http://10.0.0.5:8000/api"),
        ("", ""),
        ("ftp://example.com", ""),
        ("http://", ""),
    ],
)
def test_normalize_server_url(raw, expected):
    assert normalize_server_url(raw) == expected


@pytest.mark.parametrize(
    ("url", "insecure"),
    [
        ("http://wewin.example.com", True),
        ("http://10.0.0.5:8000", True),
        ("https://wewin.example.com", False),
        ("http://localhost:8000", False),
        ("http://127.0.0.1:8000", False),
    ],
)
def test_is_insecure_remote(url, insecure):
    assert is_insecure_remote(url) is insecure
