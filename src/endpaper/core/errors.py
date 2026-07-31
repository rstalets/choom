from __future__ import annotations

from typing import ClassVar


class EndpaperError(Exception):
    """Base. Carries the exit code the CLI should use."""

    exit_code: ClassVar[int]


class NotFoundError(EndpaperError):
    exit_code = 1


class UsageError(EndpaperError):
    exit_code = 2


class WorkspaceError(EndpaperError):
    exit_code = 3


class AssistantError(EndpaperError):
    """An assistant could not be resolved or run."""

    exit_code = 1
