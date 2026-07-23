from starlette.requests import Request

try:
    from server.server.routes.api import _is_local_admin_shortcut, _is_local_request
except ModuleNotFoundError:
    from server.routes.api import _is_local_admin_shortcut, _is_local_request


def _build_request(client_host: str, forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("utf-8")))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": headers,
        "client": (client_host, 12345),
        "scheme": "http",
        "server": ("localhost", 8000),
        "query_string": b"",
    }
    return Request(scope)


def test_is_local_request_accepts_loopback_and_private_hosts():
    assert _is_local_request(_build_request("127.0.0.1")) is True
    assert _is_local_request(_build_request("10.0.0.12")) is True
    assert _is_local_request(_build_request("172.20.0.3")) is True


def test_is_local_request_rejects_public_host():
    assert _is_local_request(_build_request("8.8.8.8")) is False


def test_local_admin_shortcut_requires_exact_credentials_and_local_request():
    local_request = _build_request("127.0.0.1")
    public_request = _build_request("8.8.8.8")

    assert _is_local_admin_shortcut(local_request, "lotradmin", "yourmommalooksfunny") is True
    assert _is_local_admin_shortcut(local_request, "lotradmin", "wrong-password") is False
    assert _is_local_admin_shortcut(local_request, "other-user", "yourmommalooksfunny") is False
    assert _is_local_admin_shortcut(public_request, "lotradmin", "yourmommalooksfunny") is False