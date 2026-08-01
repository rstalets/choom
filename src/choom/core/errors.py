from __future__ import annotations

from typing import ClassVar


class ChoomError(Exception):
    """Base. Carries the exit code the CLI should use."""

    exit_code: ClassVar[int]


class NotFoundError(ChoomError):
    exit_code = 1


class UsageError(ChoomError):
    exit_code = 2


class WorkspaceError(ChoomError):
    exit_code = 3


class AssistantError(ChoomError):
    """An assistant could not be resolved or run."""

    exit_code = 1
