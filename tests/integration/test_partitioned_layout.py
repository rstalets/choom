from __future__ import annotations

from datetime import datetime

from choom.core.meetings import create_meeting, scan_meetings
from choom.core.models import Workspace
from choom.core.notes import create_note, open_daily_note, scan_notes
from choom.tui.app import ChoomApp


async def test_collection_menu_pane_is_gone_and_its_width_returned_to_the_content_panes(
    tmp_workspace: Workspace,
) -> None:
    # FR-006: the vertical collection menu is removed; the 14 columns it used
    # go to the scope pane (fixed 14, for `YYYY-MM` + padding) and the freed
    # width goes to the list/preview split, which keeps its 2fr/3fr ratio.
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        assert len(app.screen.query("#menu-pane")) == 0
        assert len(app.screen.query("#collection-menu")) == 0

        scope_pane = app.screen.query_one("#scope-pane")
        list_pane = app.screen.query_one("#list-pane")
        preview_pane = app.screen.query_one("#preview-pane")
        assert str(scope_pane.styles.width) == "14"
        assert str(list_pane.styles.width) == "2fr"
        assert str(preview_pane.styles.width) == "3fr"


def test_meeting_lands_in_meetings_yyyy_mm(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", now=datetime(2026, 7, 28, 9, 0, 0))
    relative = meeting.path.relative_to(tmp_workspace.root).as_posix()
    assert relative.startswith("meetings/2026/07/")
    assert "2026-07-28" in relative


def test_typed_note_lands_in_notes_yyyy_mm(tmp_workspace: Workspace) -> None:
    note = create_note(
        tmp_workspace, "vendor landscape", type="research", now=datetime(2026, 7, 28, 9, 0, 0)
    )
    relative = note.path.relative_to(tmp_workspace.root).as_posix()
    assert relative.startswith("notes/2026/07/")


def test_daily_note_lands_in_notes_daily_yyyy_mm(tmp_workspace: Workspace) -> None:
    daily = open_daily_note(tmp_workspace, now=datetime(2026, 7, 28, 9, 0, 0))
    relative = daily.path.relative_to(tmp_workspace.root).as_posix()
    assert relative == "notes/daily/2026/07/2026-07-28.md"


def test_partition_directories_created_on_demand(tmp_workspace: Workspace) -> None:
    assert not (tmp_workspace.root / "meetings" / "2026").exists()
    create_meeting(tmp_workspace, "Q3 planning", now=datetime(2026, 7, 28, 9, 0, 0))
    assert (tmp_workspace.root / "meetings" / "2026" / "07").is_dir()


def test_filename_still_carries_full_iso_date(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", now=datetime(2026, 7, 28, 9, 0, 0))
    assert meeting.path.name.startswith("2026-07-28-")


def test_file_under_wrong_month_still_lists_and_is_not_moved(tmp_workspace: Workspace) -> None:
    # Frontmatter is authoritative (FR-015a): a file's directory location is not
    # re-derived from its `created` field, so a misplaced file is not corrected.
    meeting = create_meeting(tmp_workspace, "misfiled", now=datetime(2026, 7, 28, 9, 0, 0))
    wrong_dir = tmp_workspace.root / "meetings" / "2099" / "01"
    wrong_dir.mkdir(parents=True)
    misplaced = wrong_dir / meeting.path.name
    meeting.path.rename(misplaced)

    meetings, warnings = scan_meetings(tmp_workspace)
    assert warnings == []
    assert len(meetings) == 1
    assert meetings[0].path == misplaced


def test_file_directly_under_meetings_root_still_lists(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "at the root", now=datetime(2026, 7, 28, 9, 0, 0))
    root_path = tmp_workspace.root / "meetings" / meeting.path.name
    meeting.path.rename(root_path)

    meetings, warnings = scan_meetings(tmp_workspace)
    assert warnings == []
    assert len(meetings) == 1
    assert meetings[0].path == root_path


def test_workspace_with_one_daily_note_lists_exactly_one_daily_note(
    tmp_workspace: Workspace,
) -> None:
    open_daily_note(tmp_workspace, now=datetime(2026, 7, 28, 9, 0, 0))

    notes, warnings = scan_notes(tmp_workspace)
    assert warnings == []
    daily_notes = [n for n in notes if n.type == "daily"]
    assert len(daily_notes) == 1
