"""Test path resolution.

``GetTestPath()`` in ``www/common_lib.inc`` is the single function that decides
where a test lives on disk. Every stored test, every restored archive and every
URL that maps to ``results/...`` depends on it, so the layout is reproduced
literally:

* modern IDs (first ``_`` at index 6) expand ``ymd_shard_unique`` into
  ``results/YY/MM/DD/shard/unique`` (an extra path segment appears when the
  shard key itself contains ``_``)
* legacy IDs fall back to the ``olddir`` / ``oldsubdir`` settings
* anything else maps directly to ``results/<id>``
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = [
    "get_test_path",
    "absolute_test_path",
    "get_video_path",
    "ID_RE",
    "LEGACY_ID_RE",
]

ID_RE = re.compile(r"^[a-zA-Z0-9_]+$")
LEGACY_ID_RE = re.compile(r"^[0-9][0-9][0-9][0-9][0-9][0-9]_[A-Za-z0-9_]+$")


def get_test_path(
    test_id: str,
    *,
    olddir: str = "",
    oldsubdir: str = "",
    base: str = "results",
) -> str:
    """Return the path of a test relative to the web root.

    Mirrors ``GetTestPath()``. The result has no leading ``./``; the legacy
    callers prepend one when they need a relative include path.
    """

    if test_id.find("_") == 6:
        parts = test_id.split("_")
        # parts[0] is always 6 characters in this branch.
        directory = parts[1] if len(parts) > 1 else ""
        if len(parts) > 2 and parts[2]:
            directory = f"{directory}/{parts[2]}"
        year, month, day = parts[0][0:2], parts[0][2:4], parts[0][4:6]
        return f"{base}/{year}/{month}/{day}/{directory}"

    if olddir:
        if oldsubdir:
            prefix = test_id[0].upper() if test_id else ""
            return f"{base}/{olddir}/_{prefix}/{test_id}"
        return f"{base}/{olddir}/{test_id}"

    return f"{base}/{test_id}"


def absolute_test_path(
    web_root: str | Path,
    test_id: str,
    *,
    olddir: str = "",
    oldsubdir: str = "",
) -> Path:
    """Absolute filesystem path for a test directory."""

    return Path(web_root) / get_test_path(test_id, olddir=olddir, oldsubdir=oldsubdir)


def get_video_path(test_id: str, *, base: str = "results", **kwargs: str) -> str:
    """Return the video directory for a test.

    ``GetVideoPath()`` (``www/common_lib.inc``) resolves a video file, not a
    directory; this helper covers the common ``<test>/video`` convention used by
    the video pages and is refined when the video renderer is ported.
    """

    return f"{get_test_path(test_id, base=base, **kwargs)}/video"
