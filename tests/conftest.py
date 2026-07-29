from __future__ import annotations

import secrets
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pytest

from endpaper.core.models import Workspace
from endpaper.core.workspace import init_workspace


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Workspace:
    return init_workspace(tmp_path)


@pytest.fixture
def frozen_now() -> datetime:
    return datetime(2026, 7, 28, 9, 14, 0)


@pytest.fixture
def seeded_id(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    fixed = "a1b2c3d4"
    monkeypatch.setattr(secrets, "token_hex", lambda n: fixed)
    yield fixed


def daily_note_path(workspace: Workspace, day: date) -> Path:
    return workspace.daily_dir / f"{day:%Y-%m-%d}.md"
