from __future__ import annotations

from datetime import datetime

from endpaper.core.documents import scan_documents, scan_month, scan_unfiled
from endpaper.core.meetings import MEETINGS, create_meeting
from endpaper.core.models import Workspace, YearMonth
from endpaper.core.notes import NOTES, create_note


def test_scan_month_reads_only_that_month(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "january meeting", now=datetime(2026, 1, 15, 9, 0))
    create_meeting(tmp_workspace, "february meeting", now=datetime(2026, 2, 15, 9, 0))

    documents, warnings = scan_month(tmp_workspace, MEETINGS, YearMonth(2026, 1))
    assert warnings == []
    assert len(documents) == 1
    assert documents[0].title == "january meeting"


def test_scan_month_matches_scan_documents_ordering(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "first", now=datetime(2026, 1, 10, 9, 0))
    create_meeting(tmp_workspace, "second", now=datetime(2026, 1, 20, 9, 0))
    create_meeting(tmp_workspace, "third", now=datetime(2026, 1, 15, 9, 0))

    all_documents, _ = scan_documents(tmp_workspace, MEETINGS)
    month_documents, _ = scan_month(tmp_workspace, MEETINGS, YearMonth(2026, 1))
    assert [d.path for d in month_documents] == [d.path for d in all_documents]


def test_scan_month_with_no_folder_is_empty(tmp_workspace: Workspace) -> None:
    documents, warnings = scan_month(tmp_workspace, MEETINGS, YearMonth(2019, 6))
    assert documents == []
    assert warnings == []


def test_malformed_frontmatter_yields_warning_not_exception(tmp_workspace: Workspace) -> None:
    month_dir = tmp_workspace.meetings_dir / "2026" / "01"
    month_dir.mkdir(parents=True)
    (month_dir / "broken.md").write_text("no frontmatter here", encoding="utf-8")

    documents, warnings = scan_month(tmp_workspace, MEETINGS, YearMonth(2026, 1))
    assert documents == []
    assert len(warnings) == 1
    assert warnings[0].reason == "no_frontmatter"


def test_scan_unfiled_reaches_stray_files_scan_month_cannot(tmp_workspace: Workspace) -> None:
    create_note(tmp_workspace, "filed note", now=datetime(2026, 1, 15, 9, 0))
    stray = tmp_workspace.notes_dir / "idea.md"
    stray.write_text("stray note, no frontmatter", encoding="utf-8")

    month_documents, _ = scan_month(tmp_workspace, NOTES, YearMonth(2026, 1))
    assert all(d.title != "stray note" for d in month_documents)

    unfiled_documents, unfiled_warnings = scan_unfiled(tmp_workspace, NOTES)
    assert len(unfiled_warnings) == 1
    assert unfiled_warnings[0].path == stray


def test_scan_unfiled_empty_when_nothing_stray(tmp_workspace: Workspace) -> None:
    create_note(tmp_workspace, "filed note", now=datetime(2026, 1, 15, 9, 0))
    documents, warnings = scan_unfiled(tmp_workspace, NOTES)
    assert documents == []
    assert warnings == []
