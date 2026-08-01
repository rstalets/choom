from __future__ import annotations

import os
from pathlib import Path

import pytest

from endpaper.core.atomic_write import write_text_atomic
from endpaper.core.errors import WorkspaceError


def test_writes_the_target_and_leaves_no_temp_file(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    write_text_atomic(path, "hello\n")

    assert path.read_text(encoding="utf-8") == "hello\n"
    assert list(tmp_path.iterdir()) == [path]


def test_creates_the_parent_directory_if_missing(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b" / "doc.md"
    write_text_atomic(path, "hello\n")

    assert path.read_text(encoding="utf-8") == "hello\n"


def test_overwrite_replaces_content_atomically(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text("original\n", encoding="utf-8")

    write_text_atomic(path, "replaced\n")

    assert path.read_text(encoding="utf-8") == "replaced\n"
    assert list(tmp_path.iterdir()) == [path]


def test_failed_replace_raises_workspace_error_and_leaves_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "doc.md"
    path.write_text("original\n", encoding="utf-8")

    def _boom(*args: object, **kwargs: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", _boom)

    with pytest.raises(WorkspaceError):
        write_text_atomic(path, "replaced\n")

    assert path.read_text(encoding="utf-8") == "original\n"
    assert list(tmp_path.iterdir()) == [path]
