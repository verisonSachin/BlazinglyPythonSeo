"""Shared exception types.

The legacy code frequently signals failure by side effect rather than by
throwing: ``ValidateTestId()`` calls ``exit(0)`` and many endpoints answer
HTTP 200 with ``statusCode: 400`` in the body. Those behaviours are part of the
public contract, so they are modelled explicitly here instead of being replaced
with ordinary HTTP error responses.
"""

from __future__ import annotations

from .phpini import IniParseError

__all__ = ["WptError", "InvalidTestId", "IniParseError"]


class WptError(Exception):
    """Base class for expected, client-visible failures."""


class InvalidTestId(WptError):
    """A test ID failed validation.

    Legacy behaviour (``ValidateTestId()`` in ``www/common_lib.inc``) is to
    ``exit(0)``: HTTP 200 with an empty body. Callers must translate this into
    :class:`EmptyResponse` rather than a 400.
    """

    def __init__(self, test_id: str) -> None:
        super().__init__(f"invalid test id: {test_id!r}")
        self.test_id = test_id
