"""Shared helpers for differential tests."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.layout import find_www_root, repo_root

REPO_ROOT = repo_root()
WWW = find_www_root()
SETTINGS_DIR = WWW / "settings"

PHP = shutil.which("php")


def php_parse_ini(path: Path, *, sections: bool = False) -> dict:
    """Return PHP's own ``parse_ini_file`` output for differential assertions."""

    if PHP is None:  # pragma: no cover - environment dependent
        pytest.skip("php binary not available")

    script = (
        "$r = @parse_ini_file($argv[1], $argv[2] === '1');"
        "if ($r === false) { fwrite(STDERR, 'parse failed'); exit(3); }"
        "echo json_encode($r, JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_PRESERVE_ZERO_FRACTION);"
    )
    proc = subprocess.run(
        [PHP, "-r", script, str(path), "1" if sections else "0"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"php parse failed for {path}: {proc.stderr}")
    return json.loads(proc.stdout)


def ini_files(settings_dir: Path = SETTINGS_DIR) -> list[Path]:
    """Every INI file shipped with the reference tree, sample or live."""

    if not settings_dir.is_dir():
        return []
    return [
        p
        for p in sorted(settings_dir.rglob("*"))
        if p.is_file() and (p.name.endswith(".ini") or p.name.endswith(".ini.sample"))
    ]
