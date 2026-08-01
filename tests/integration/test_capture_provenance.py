from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import Label, ListView

from choom.cli.main import main
from choom.core.links import inbound_links
from choom.core.meetings import create_meeting
from choom.core.mirrors import capture_task
from choom.core.models import Task, Workspace
from choom.core.tasks import set_task_state
from choom.tui.app import ChoomApp
from tests.helpers import to_collection


def _capture(tmp_workspace: Workspace) -> tuple[Task, str]:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, _line = capture_task(
        tmp_workspace,
        "call Terry about the renewal",
        source=meeting.path,
        source_id=meeting.id,
    )
    return task, meeting.id


# --- T023: a captured task is an inbound link of its meeting, both adapters ------


def test_captured_task_is_an_inbound_link_of_the_meeting_core(tmp_workspace: Workspace) -> None:
    task, meeting_id = _capture(tmp_workspace)

    inbound = inbound_links(tmp_workspace, meeting_id)
    assert any(link.target_id == meeting_id and link.text == task.text for link in inbound)


def test_captured_task_is_an_inbound_link_of_the_meeting_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    from choom.core.workspace import find_workspace

    workspace = find_workspace(tmp_path)
    _task, meeting_id = _capture(workspace)

    exit_code = main(["links", meeting_id, "--direction", "in", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0

    payload = json.loads(captured.out)
    assert any(entry["target_id"] == meeting_id for entry in payload)


# --- T024: the link survives the source document moving -------------------------


def test_link_still_resolves_after_the_source_document_moves(tmp_workspace: Workspace) -> None:
    task, meeting_id = _capture(tmp_workspace)
    assert task.id is not None

    meeting_path = next(tmp_workspace.meetings_dir.rglob("*.md"))
    new_dir = tmp_workspace.meetings_dir / "2020" / "01"
    new_dir.mkdir(parents=True)
    new_path = new_dir / meeting_path.name
    meeting_path.rename(new_path)

    from choom.core.links import resolve_id

    target, warnings = resolve_id(tmp_workspace, meeting_id)
    assert target is not None
    assert target.path == new_path
    assert not any(w.reason == "link_dead" for w in warnings)


# --- T025: a deleted source document produces a link_dead warning ---------------


def test_deleted_source_document_produces_a_dead_link_warning(tmp_workspace: Workspace) -> None:
    task, meeting_id = _capture(tmp_workspace)
    assert task.id is not None

    meeting_path = next(tmp_workspace.meetings_dir.rglob("*.md"))
    meeting_path.unlink()

    from choom.core.links import outbound_for_target, resolve_id

    target, _warnings = resolve_id(tmp_workspace, task.id)
    assert target is not None
    reports = outbound_for_target(tmp_workspace, target)
    assert len(reports) == 1
    link, status = reports[0]
    assert status == "dead"
    assert link.target_id == meeting_id

    # The link itself is untouched -- still names the (now-missing) meeting.
    line = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert f"links:{meeting_id}" in line

    # Nothing raises when the task is otherwise used, e.g. toggled.
    set_task_state(tmp_workspace, task.id, done=True)


# --- T026: the task preview names its originating document, and the open key ---
# --- reaches it. 008's Links pane already renders this; this is the assertion. -


async def test_task_preview_names_the_meeting_and_opens_it(tmp_workspace: Workspace) -> None:
    task, _meeting_id = _capture(tmp_workspace)

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "tasks")

        await pilot.press("b")
        await pilot.pause()

        rows = app.screen.query_one("#preview-links-list", ListView)
        rendered = "\n".join(str(label.content) for label in rows.query(Label))
        assert "Points at" in rendered
        assert "Q3 planning" in rendered

        from choom.tui.links_pane import LinkRow

        link_rows = [child for child in rows.children if isinstance(child, LinkRow)]
        outbound = next(row for row in link_rows if row.direction == "out")
        rows.index = list(rows.children).index(outbound)
        await pilot.press("enter")
        await pilot.pause()

        from choom.tui.preview_screen import PreviewScreen

        assert isinstance(app.screen, PreviewScreen)
        assert app.screen.document is not None
        assert app.screen.document.title == "Q3 planning"
