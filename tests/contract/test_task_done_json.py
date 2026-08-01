from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from endpaper.cli.main import main
from endpaper.core.documents import _read_document
from endpaper.core.mirrors import capture_task
from endpaper.core.workspace import find_workspace

EXPECTED_KEYS = {"id", "done", "links", "documents_updated", "warnings"}


@pytest.fixture
def cli_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> Path:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    return tmp_path


def _capture_linked_task(cli_root: Path, capsys: pytest.CaptureFixture[str]) -> tuple[str, Path]:
    main(["meeting", "new", "Q3 planning"])
    meeting_rel = capsys.readouterr().out.strip()
    workspace = find_workspace(cli_root)
    meeting_path = workspace.root / meeting_rel
    meeting_id = _read_document(meeting_path).id  # type: ignore[union-attr]

    task, line = capture_task(workspace, "call Terry", source=meeting_path, source_id=meeting_id)
    assert task.id is not None
    text = meeting_path.read_text(encoding="utf-8")
    meeting_path.write_text(text + line + "\n", encoding="utf-8")
    return task.id, meeting_path


def test_task_done_json_schema(cli_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    task_id, meeting_path = _capture_linked_task(cli_root, capsys)

    exit_code = main(["task", "done", task_id, "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0

    payload = json.loads(captured.out)
    assert set(payload.keys()) == EXPECTED_KEYS
    assert payload["id"] == task_id
    assert payload["done"] is True
    assert isinstance(payload["links"], list)
    assert len(payload["links"]) == 1
    assert payload["warnings"] == []


def test_documents_updated_lists_only_documents_actually_written(
    cli_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    task_id, meeting_path = _capture_linked_task(cli_root, capsys)

    exit_code = main(["task", "done", task_id, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0

    assert payload["documents_updated"] == [meeting_path.relative_to(cli_root).as_posix()]
    for path in payload["documents_updated"]:
        assert "\\" not in path

    # Toggling again to the same state a second time in a row (no-op) writes
    # nothing further -- but here we flip it back open, which is a real change.
    exit_code = main(["task", "undone", task_id, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["documents_updated"] == [meeting_path.relative_to(cli_root).as_posix()]


def test_stream_separation_on_an_unwritable_linked_document(
    cli_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    task_id, meeting_path = _capture_linked_task(cli_root, capsys)

    # Complete it once, successfully, while the directory is still writable --
    # the mirror now reads [x]. Then lock the directory down and reopen the
    # task, so the mirror genuinely needs a splice it cannot make.
    main(["task", "done", task_id, "--json"])
    capsys.readouterr()

    directory = meeting_path.parent
    original_mode = directory.stat().st_mode
    directory.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        exit_code = main(["task", "undone", task_id, "--json"])
        captured = capsys.readouterr()

        assert exit_code == 0
        payload = json.loads(captured.out)  # parses cleanly despite the warning
        assert payload["warnings"] != []
        assert payload["documents_updated"] == []
        assert meeting_path.name in captured.err
        assert captured.err.startswith("endpaper: ")  # the human-readable form
    finally:
        directory.chmod(original_mode)
