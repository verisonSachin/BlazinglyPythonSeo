"""FastAPI wiring."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import AppConfig, create_app


def make_app(tmp_path: Path) -> TestClient:
    config = AppConfig(
        www_root=tmp_path,
        settings_dir=tmp_path / "settings",
        tmp_dir=tmp_path / "tmp",
        results_dir=tmp_path / "results",
        jobs_dir=tmp_path / "work" / "jobs",
    )
    return TestClient(create_app(config))


def test_health_endpoint(tmp_path: Path) -> None:
    client = make_app(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["settings_dir"] == str(tmp_path / "settings")


def test_version_endpoint(tmp_path: Path) -> None:
    client = make_app(tmp_path)
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["compat"] == "legacy-php"


def test_openapi_is_namespaced(tmp_path: Path) -> None:
    client = make_app(tmp_path)
    assert client.get("/api/v1/openapi.json").status_code == 200
