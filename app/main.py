"""FastAPI application factory.

Only infrastructure lives here for now. Legacy-compatible routers
(``/runtest.php``, ``/work/*``, ...) are mounted as they are ported; the goal is
that every mounted route matches the PHP contract exactly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, FastAPI, Request

from .core.layout import find_settings_dir, find_www_root
from .core.settings import Settings

__all__ = ["create_app", "get_settings", "AppConfig"]


@dataclass(frozen=True)
class AppConfig:
    """Process-level configuration (paths only; feature flags live in settings)."""

    www_root: Path
    settings_dir: Path
    tmp_dir: Path
    results_dir: Path
    jobs_dir: Path


def _config_from_env() -> AppConfig:
    www_root = find_www_root()
    settings_dir = find_settings_dir()
    return AppConfig(
        www_root=www_root,
        settings_dir=settings_dir,
        tmp_dir=Path(os.environ.get("WPT_TMP_DIR", www_root / "tmp")).resolve(),
        results_dir=Path(os.environ.get("WPT_RESULTS_DIR", www_root / "results")).resolve(),
        jobs_dir=Path(os.environ.get("WPT_JOBS_DIR", www_root / "work" / "jobs")).resolve(),
    )


def create_app(config: AppConfig | None = None) -> FastAPI:
    app = FastAPI(
        title="WebPageTest compatibility backend",
        version="0.1.0",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
    )
    app.state.config = config or _config_from_env()
    app.state.settings = Settings(app.state.config.settings_dir)

    @app.get("/health", include_in_schema=False)
    def health(request: Request) -> dict[str, object]:
        cfg: AppConfig = request.app.state.config
        settings: Settings = request.app.state.settings
        return {
            "status": "ok",
            "version": request.app.version,
            "www_root": str(cfg.www_root),
            "settings_dir": str(cfg.settings_dir),
            "settings_loaded": len(settings.load()),
        }

    @app.get("/api/v1/version", tags=["meta"])
    def version(request: Request) -> dict[str, str]:
        return {
            "application": "webpagetest-compat",
            "version": request.app.version,
            "compat": "legacy-php",
        }

    return app


def get_settings(request: Request) -> Settings:
    """FastAPI dependency returning the process settings reader."""

    return request.app.state.settings


app = create_app()
