"""The API's security boundary: capabilities, headers, docs, settings, static files."""

from __future__ import annotations

from pathlib import Path

import pytest

from maplegotchi.api.app import create_app
from maplegotchi.config import DEV_ORIGINS, Mode, Settings, SettingsError, settings_from_env
from tests.api.support import TRUSTED, make_client, make_service, make_settings, production

EXPECTED_ROUTES = {
    ("GET", "/api/health"),
    ("GET", "/api/snapshot"),
    ("GET", "/api/maple"),
    ("GET", "/api/status"),
    ("GET", "/api/observations/latest"),
    ("GET", "/api/server"),
    ("GET", "/api/journal"),
    ("GET", "/api/timeline"),
    ("GET", "/api/events"),
    ("POST", "/api/interactions/greet"),
    ("POST", "/api/interactions/pet"),
}


def api_routes(app) -> set[tuple[str, str]]:  # type: ignore[no-untyped-def]
    """Every public operation, from the app's own OpenAPI description."""
    paths = app.openapi()["paths"]
    return {(method.upper(), path) for path, ops in paths.items() for method in ops}


def test_route_table_is_exactly_the_approved_surface(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    app = create_app(service, make_settings(tmp_path), run_life_loop=False)
    routes = api_routes(app)
    assert routes == EXPECTED_ROUTES
    mutating = {r for r in routes if r[0] != "GET"}
    assert mutating == {("POST", "/api/interactions/greet"), ("POST", "/api/interactions/pet")}
    banned = {
        "admin",
        "debug",
        "exec",
        "shell",
        "command",
        "action",
        "actions",
        "chat",
        "feed",
        "gift",
        "shop",
        "control",
        "restart",
        "systemctl",
    }
    assert not [p for _, p in routes if banned & set(p.split("/"))]
    service.close()


def test_production_has_no_docs_or_openapi(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path, **production(tmp_path))
    for path in ("/api/docs", "/api/openapi.json", "/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
    dev = make_client(service, tmp_path)
    assert dev.get("/api/openapi.json").status_code == 200
    service.close()


def test_production_origin_is_the_configured_one_only(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path, **production(tmp_path))
    assert client.post("/api/interactions/greet", headers=TRUSTED).status_code == 403  # dev origin
    ok = client.post("/api/interactions/greet", headers={"Origin": "https://maple.tailnet.example"})
    assert ok.status_code == 200
    service.close()


def test_security_headers_and_no_cors(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path)
    for response in (
        client.get("/api/snapshot", headers={"Origin": "http://evil.example"}),
        client.post("/api/interactions/pet", headers=TRUSTED),
        client.options("/api/interactions/pet", headers={"Origin": "http://evil.example",
                                                          "Access-Control-Request-Method": "POST"}),
    ):  # fmt: skip
        headers = response.headers
        assert "frame-ancestors 'none'" in headers["content-security-policy"]
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert headers["cache-control"] == "no-store"
        assert "access-control-allow-origin" not in headers  # no CORS, ever
        assert "server" not in headers
    service.close()


def test_declared_oversized_body_rejected_before_routing(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path)
    response = client.post("/api/snapshot", content=b"x" * 2048, headers=TRUSTED)
    assert response.status_code == 413
    service.close()


# ---------------------------------------------------------------- settings


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "100.64.0.1", "::", "example.com"])  # noqa: S104
def test_only_loopback_binds_are_allowed(tmp_path: Path, host: str) -> None:
    with pytest.raises(SettingsError):
        Settings(data_dir=tmp_path, host=host)


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_loopback_binds(tmp_path: Path, host: str) -> None:
    assert Settings(data_dir=tmp_path, host=host).host == host


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "http://*.example",
        "https://maple.example/path",
        "maple.example",
        "ftp://x",
        "https://a b",
    ],
)
def test_origins_must_be_exact(tmp_path: Path, origin: str) -> None:
    with pytest.raises(SettingsError):
        Settings(data_dir=tmp_path, allowed_origins=(origin,))


def test_production_requires_explicit_origins(tmp_path: Path) -> None:
    with pytest.raises(SettingsError):
        Settings(data_dir=tmp_path, mode=Mode.PRODUCTION, allowed_origins=())
    with pytest.raises(SettingsError):
        settings_from_env({"MAPLE_DATA_DIR": str(tmp_path), "MAPLE_MODE": "production"})


def test_settings_from_env(tmp_path: Path) -> None:
    dev = settings_from_env({"MAPLE_DATA_DIR": str(tmp_path)})
    assert dev.allowed_origins == DEV_ORIGINS and dev.host == "127.0.0.1" and dev.port == 8470
    prod = settings_from_env({
        "MAPLE_DATA_DIR": str(tmp_path), "MAPLE_MODE": "production",
        "MAPLE_ALLOWED_ORIGINS": "https://maple.tailnet.example, https://paolo-core.tailnet.example",
        "MAPLE_HEARTBEAT_SECONDS": "300", "MAPLE_SENSES": "fake",
    })  # fmt: skip
    assert prod.allowed_origins == (
        "https://maple.tailnet.example",
        "https://paolo-core.tailnet.example",
    )
    assert prod.docs_enabled is False
    with pytest.raises(SettingsError):
        settings_from_env({})


# ---------------------------------------------------------------- static frontend


def build_dist(root: Path) -> Path:
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Maple</title>", encoding="utf-8")
    (dist / "assets" / "app-123.js").write_text("console.log('maple')", encoding="utf-8")
    (root / "secret.txt").write_text("outside the dist", encoding="utf-8")
    return dist


def test_static_frontend_and_spa_fallback(tmp_path: Path) -> None:
    service = make_service(tmp_path / "data")
    client = make_client(service, tmp_path, static_dir=build_dist(tmp_path))
    index = client.get("/")
    assert index.status_code == 200 and "<title>Maple</title>" in index.text
    assert index.headers["cache-control"] == "no-cache"
    deep = client.get("/room/journal")
    assert deep.status_code == 200 and "<title>Maple</title>" in deep.text  # SPA fallback
    asset = client.get("/assets/app-123.js")
    assert asset.status_code == 200 and "immutable" in asset.headers["cache-control"]
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/favicon.ico").status_code == 404
    # API routes are never shadowed by the fallback.
    assert client.get("/api/health").json() == {"status": "ok"}
    unknown = client.get("/api/does-not-exist")
    assert unknown.status_code == 404 and unknown.headers["content-type"].startswith(
        "application/json"
    )
    assert client.get("/api").status_code == 404
    for escape in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"):
        response = client.get(escape)
        assert "outside the dist" not in response.text, escape
    service.close()


def test_static_dir_without_index_fails_at_startup(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    service = make_service(tmp_path / "data")
    with pytest.raises(FileNotFoundError):
        create_app(service, make_settings(tmp_path, static_dir=empty), run_life_loop=False)
    service.close()
