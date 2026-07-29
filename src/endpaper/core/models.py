from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path

    @property
    def meetings_dir(self) -> Path:
        return self.root / "meetings"


@dataclass(frozen=True, slots=True)
class Meeting:
    id: str
    path: Path
    title: str
    type: str
    tags: tuple[str, ...]
    created: str
    updated: str


ScanWarningReason = Literal[
    "no_frontmatter",
    "unterminated_frontmatter",
    "malformed_yaml",
    "not_a_mapping",
    "missing_fields",
    "unexpected_fields",
    "invalid_value",
]


@dataclass(frozen=True, slots=True)
class ScanWarning:
    path: Path
    reason: ScanWarningReason
    message: str


@dataclass(frozen=True, slots=True)
class MeetingFilter:
    type: str | None = None
    tags: tuple[str, ...] = ()
    since: date | None = None
