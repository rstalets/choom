from __future__ import annotations

import os
from pathlib import Path

import pytest

from endpaper.core.editing import load_for_edit, save_buffer


def test_failed_replace_leaves_target_untouched_and_no_temp_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "doc.md"
    original = "---\nid: meeting_1\nupdated: 2026-01-01T09:00:00\n---\nbody\n"
    path.write_text(original, encoding="utf-8")
    original_bytes = path.read_bytes()

    def _boom(*args: object, **kwargs: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", _boom)

    file = load_for_edit(path)
    result = save_buffer(path, file.text + "\nnew content", file)

    assert result.ok is False
    assert result.message != ""
    assert path.read_bytes() == original_bytes
    assert list(tmp_path.iterdir()) == [path]
