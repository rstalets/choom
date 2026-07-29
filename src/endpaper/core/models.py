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

    @property
    def notes_dir(self) -> Path:
        return self.root / "notes"

    @property
    def daily_dir(self) -> Path:
        return self.root / "notes" / "daily"


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    path: Path
    title: str
    type: str
    tags: tuple[str, ...]
    created: str
    updated: str


Meeting = Document
Note = Document


@dataclass(frozen=True, slots=True)
class Collection:
    id_prefix: str
    create_dir: str
    scan_dirs: tuple[str, ...]
    reserved_types: frozenset[str]


@dataclass(frozen=True, slots=True)
class DailyNote:
    path: Path
    document: Document | None
    created: bool


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
class DocumentFilter:
    type: str | None = None
    tags: tuple[str, ...] = ()
    since: date | None = None


MeetingFilter = DocumentFilter
