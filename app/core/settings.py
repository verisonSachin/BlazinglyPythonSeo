"""Settings loading with the legacy precedence rules.

Two different precedence models exist in the PHP application and both must be
preserved:

``Util::getSetting()`` (``www/src/Util.php``)
    Merges ``settings.ini`` then ``common/settings.ini`` then
    ``server/settings.ini`` with ``array_merge``: later files win, and keys that
    only exist in an earlier file survive. The merged array is cached for 60s.

``SettingsFileReader::ini()`` (``www/src/Util/SettingsFileReader.php``)
    Looks for the *first* existing file in the order ``server/``, ``common/``,
    base, ``.sample``. Files are **not** merged: whichever is found first is
    returned whole.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Mapping

from .cache import TTLCache
from .phpini import parse_ini_file

__all__ = ["Settings", "SETTINGS_CACHE_TTL", "SERVER_SECRET_TTL", "SERVER_SECRET_MISSING_TTL"]

SETTINGS_CACHE_TTL = 60.0
SERVER_SECRET_TTL = 3600.0
SERVER_SECRET_MISSING_TTL = 60.0

_SETTINGS_KEY = "settings"
_SERVER_SECRET_KEY = "server-secret"


class Settings:
    """Read-only view over ``www/settings`` with APCu-compatible caching."""

    def __init__(
        self,
        settings_dir: str | os.PathLike[str],
        *,
        cache: TTLCache | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.settings_dir = Path(settings_dir)
        self._cache = cache if cache is not None else TTLCache()
        self._environ = environ

    # ------------------------------------------------------------------
    # merged settings (Util::getSetting)
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Return the merged settings array (cached for 60s)."""

        cached = self._cache.fetch(_SETTINGS_KEY)
        if isinstance(cached, dict) and cached:
            return cached

        merged: dict[str, Any] = {}
        for candidate in (
            self.settings_dir / "settings.ini",
            self.settings_dir / "common" / "settings.ini",
            self.settings_dir / "server" / "settings.ini",
        ):
            if candidate.is_file():
                merged.update(parse_ini_file(candidate, environ=self._environ))

        self._cache.store(_SETTINGS_KEY, merged, SETTINGS_CACHE_TTL)
        return merged

    def get(self, name: str, default: Any = False) -> Any:
        """Equivalent to ``GetSetting($name, $default)``."""

        return self.load().get(name, default)

    def get_str(self, name: str, default: str = "") -> str:
        """Get a setting coerced to ``str`` (legacy values are always strings)."""

        value = self.get(name, default)
        if value is False or value is None:
            return default
        return str(value)

    def get_int(self, name: str, default: int = 0) -> int:
        """Get a setting coerced like PHP's ``(int)`` cast."""

        value = self.get(name, default)
        if value is False or value is None or value == "":
            return default
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    def get_bool(self, name: str, default: bool = False) -> bool:
        """Get a setting coerced like PHP truthiness.

        ``"0"`` and ``""`` are false; any other non-empty string is true.
        """

        value = self.get(name, default)
        if isinstance(value, bool):
            return value
        if value is False or value is None:
            return False
        return str(value) not in ("", "0")

    def reload(self) -> None:
        """Drop the cached merge (used by ``cli/clearCache`` equivalents)."""

        self._cache.delete(_SETTINGS_KEY)

    # ------------------------------------------------------------------
    # server secret (Util::getServerSecret)
    # ------------------------------------------------------------------

    def server_secret(self) -> str:
        """Return the ``[server] secret`` from ``keys.ini``.

        Precedence is base -> ``common/`` -> ``server/`` where a later file
        replaces the earlier one entirely. The empty string is cached for 60s
        so a missing keys file does not force a parse on every request.
        """

        cached = self._cache.fetch(_SERVER_SECRET_KEY)
        if isinstance(cached, str):
            return cached
        if cached is not None and not isinstance(cached, str):
            cached = None

        keys_file = self.settings_dir / "keys.ini"
        for override in (self.settings_dir / "common" / "keys.ini", self.settings_dir / "server" / "keys.ini"):
            if override.is_file():
                keys_file = override

        secret: str | None = None
        if keys_file.is_file():
            keys = parse_ini_file(keys_file, process_sections=True, environ=self._environ)
            server = keys.get("server")
            if isinstance(server, dict) and "secret" in server:
                value = server["secret"]
                if isinstance(value, str):
                    secret = value.strip()

        if secret is None:
            self._cache.store(_SERVER_SECRET_KEY, "", SERVER_SECRET_MISSING_TTL)
            return ""
        self._cache.store(_SERVER_SECRET_KEY, secret, SERVER_SECRET_TTL)
        return secret

    # ------------------------------------------------------------------
    # cookies (Util::getCookieName)
    # ------------------------------------------------------------------

    def cookie_name(self, name: str) -> str:
        """Derive the obfuscated cookie name used for a logical cookie.

        Must match PHP exactly or every existing session is invalidated::

            sha256( sha1(name + cookie_secret) + server_secret )
        """

        cookie_secret = self.get_str("cookie_secret", "x")
        inner = hashlib.sha1(f"{name}{cookie_secret}".encode("utf-8")).hexdigest()
        return hashlib.sha256(f"{inner}{self.server_secret()}".encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # SettingsFileReader::ini / ::plain
    # ------------------------------------------------------------------

    def ini_file(
        self,
        filename: str,
        *,
        process_sections: bool = False,
        allow_sample: bool = False,
    ) -> dict[str, Any] | None:
        """Return the first existing candidate file, parsed.

        Order is ``server/``, ``common/``, base, then ``<filename>.sample``
        when ``allow_sample`` is set. Unlike :meth:`load`, files are not merged.
        """

        candidates = [
            self.settings_dir / "server" / filename,
            self.settings_dir / "common" / filename,
            self.settings_dir / filename,
        ]
        if allow_sample:
            candidates.append(self.settings_dir / f"{filename}.sample")

        for candidate in candidates:
            if candidate.is_file():
                return parse_ini_file(candidate, process_sections, environ=self._environ)
        return None

    def plain_file(self, filename: str) -> list[str] | None:
        """Return stripped non-empty lines, or ``None`` when no file exists.

        Mirrors ``SettingsFileReader::plain()`` with its default flags
        (``FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES``).
        """

        candidates = [
            self.settings_dir / "server" / filename,
            self.settings_dir / "common" / filename,
            self.settings_dir / filename,
        ]
        for candidate in candidates:
            if candidate.is_file():
                lines = candidate.read_text(encoding="utf-8", errors="surrogateescape").splitlines()
                return [line for line in lines if line != ""]
        return None
