from __future__ import annotations

from pathlib import Path

import pytest

from choom.cli.main import main
from choom.core.mirrors import mirror_line
from choom.core.tasks import get_task
from choom.core.workspace import find_workspace


@pytest.fixture
def cli_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> Path:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    return tmp_path


def test_link_with_a_resolvable_id_records_it(
    cli_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["meeting", "new", "Q3 planning"])
    meeting_path = capsys.readouterr().out.strip()
    workspace = find_workspace(cli_root)
    from choom.core.documents import _read_document

    meeting_id = _read_document(workspace.root / meeting_path).id  # type: ignore[union-attr]

    exit_code = main(["task", "add", "call Terry", "--link", meeting_id])
    task_id = capsys.readouterr().out.strip()
    assert exit_code == 0

    task = get_task(workspace, task_id)
    assert task.links == (meeting_id,)


def test_link_supplied_twice_records_both_in_order(
    cli_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["meeting", "new", "Q3 planning"])
    first_path = capsys.readouterr().out.strip()
    main(["meeting", "new", "Q4 planning"])
    second_path = capsys.readouterr().out.strip()

    workspace = find_workspace(cli_root)
    from choom.core.documents import _read_document

    first_id = _read_document(workspace.root / first_path).id  # type: ignore[union-attr]
    second_id = _read_document(workspace.root / second_path).id  # type: ignore[union-attr]

    main(["task", "add", "call Terry", "--link", first_id, "--link", second_id])
    task_id = capsys.readouterr().out.strip()

    task = get_task(workspace, task_id)
    assert task.links == (first_id, second_id)


def test_cli_linked_task_line_matches_the_editors_shape(
    cli_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["meeting", "new", "Q3 planning"])
    meeting_path = capsys.readouterr().out.strip()
    workspace = find_workspace(cli_root)
    from choom.core.documents import _read_document
    from choom.core.mirrors import capture_task

    meeting_id = _read_document(workspace.root / meeting_path).id  # type: ignore[union-attr]

    # The editor's path.
    editor_task, editor_line = capture_task(
        workspace,
        "call Terry from the editor",
        source=workspace.root / meeting_path,
        source_id=meeting_id,
    )

    # The CLI's path.
    main(["task", "add", "call Terry from the CLI", "--link", meeting_id])
    cli_task_id = capsys.readouterr().out.strip()
    cli_task = get_task(workspace, cli_task_id)

    assert cli_task.links == editor_task.links
    cli_line = mirror_line(
        cli_task, source=workspace.root / meeting_path, tasks_file=workspace.tasks_file
    )
    # Same shape: a checklist item whose link points at tasks.md#<id>.
    assert cli_line.startswith("- [ ] [")
    assert f"tasks.md#{cli_task_id}" in cli_line
    assert editor_line.startswith("- [ ] [")
    assert f"tasks.md#{editor_task.id}" in editor_line


def test_unresolvable_link_id_exits_1_names_it_on_stderr_and_creates_nothing(
    cli_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["task", "add", "call Terry", "--link", "meeting_20260101_deadbeef"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "meeting_20260101_deadbeef" in captured.err
    assert captured.out == ""

    workspace = find_workspace(cli_root)
    assert (
        not workspace.tasks_file.exists()
        or workspace.tasks_file.read_text(encoding="utf-8").strip() == ""
    )


def test_a_genuine_usage_error_still_exits_2(
    cli_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["task", "add"])  # missing the required description argument
    assert exit_code == 2
