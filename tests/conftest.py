from __future__ import annotations

import secrets
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pytest

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.core.workspace import init_workspace


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Workspace:
    return init_workspace(tmp_path).workspace


@pytest.fixture
def frozen_now() -> datetime:
    return datetime(2026, 7, 28, 9, 14, 0)


@pytest.fixture
def seeded_id(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    fixed = "a1b2c3d4"
    monkeypatch.setattr(secrets, "token_hex", lambda n: fixed)
    yield fixed


@pytest.fixture
def sample_document(tmp_workspace: Workspace) -> Path:
    meeting = create_meeting(tmp_workspace, "sample meeting", type="standup")
    return meeting.path


def write_raw(path: Path, text: str, *, newline: str) -> None:
    """Write `text` (authored with plain "\\n") to `path` using `newline` as the line
    ending, with Python's own newline translation switched off so the bytes on disk are
    exactly what was requested -- no double translation."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\n", newline))


def daily_note_path(workspace: Workspace, day: date) -> Path:
    return workspace.daily_dir / f"{day:%Y/%m}" / f"{day:%Y-%m-%d}.md"


def tasks_file(workspace: Workspace) -> Path:
    return workspace.root / "tasks.md"


def write_tasks(workspace: Workspace, text: str, *, newline: str = "\n") -> Path:
    path = tasks_file(workspace)
    with open(path, "w", encoding="utf-8", newline=newline) as fh:
        fh.write(text)
    return path
