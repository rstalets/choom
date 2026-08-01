from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from choom.core.documents import list_months
from choom.core.meetings import MEETINGS, create_meeting
from choom.core.models import Workspace, YearMonth
from choom.core.notes import NOTES, create_note, open_daily_note


def test_current_month_always_present_even_with_no_documents(tmp_workspace: Workspace) -> None:
    listing = list_months(tmp_workspace, MEETINGS)
    today = date.today()
    assert YearMonth(today.year, today.month) in listing.months
    assert listing.has_unfiled is False


def test_months_are_ordered_most_recent_first(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "jan", now=datetime(2026, 1, 15, 9, 0))
    create_meeting(tmp_workspace, "mar", now=datetime(2026, 3, 15, 9, 0))
    create_meeting(tmp_workspace, "feb", now=datetime(2026, 2, 15, 9, 0))

    listing = list_months(tmp_workspace, MEETINGS)
    ordered = [m for m in listing.months if m.year == 2026 and m.month in (1, 2, 3)]
    assert ordered == [YearMonth(2026, 3), YearMonth(2026, 2), YearMonth(2026, 1)]


def test_daily_subtree_dedupes_into_the_same_month(tmp_workspace: Workspace) -> None:
    when = datetime(2026, 7, 15, 9, 0)
    create_note(tmp_workspace, "regular note", now=when)
    open_daily_note(tmp_workspace, now=when)

    listing = list_months(tmp_workspace, NOTES)
    matches = [m for m in listing.months if m == YearMonth(2026, 7)]
    assert len(matches) == 1


def test_junk_directory_names_are_ignored_not_fatal(tmp_workspace: Workspace) -> None:
    (tmp_workspace.meetings_dir / "archive").mkdir(parents=True)
    (tmp_workspace.meetings_dir / "2026" / "13").mkdir(parents=True)  # invalid month
    (tmp_workspace.meetings_dir / "20xy" / "01").mkdir(parents=True)  # not a real year

    listing = list_months(tmp_workspace, MEETINGS)
    assert YearMonth(2026, 13) not in [m for m in listing.months if m.year == 2026]
    assert all(m.month != 13 for m in listing.months)


def test_missing_scan_dir_yields_no_error(tmp_workspace: Workspace) -> None:
    listing = list_months(tmp_workspace, MEETINGS)
    assert isinstance(listing.months, tuple)


def test_opens_zero_files(tmp_workspace: Workspace, monkeypatch: pytest.MonkeyPatch) -> None:
    create_meeting(tmp_workspace, "one", now=datetime(2026, 1, 15, 9, 0))
    create_meeting(tmp_workspace, "two", now=datetime(2026, 2, 15, 9, 0))

    def _forbidden(self: Path, *args: object, **kwargs: object) -> str:
        raise AssertionError(f"list_months must not read file contents, tried {self}")

    monkeypatch.setattr(Path, "read_text", _forbidden)
    list_months(tmp_workspace, MEETINGS)


def test_has_unfiled_true_when_stray_markdown_exists(tmp_workspace: Workspace) -> None:
    stray = tmp_workspace.notes_dir / "idea.md"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("stray note", encoding="utf-8")

    listing = list_months(tmp_workspace, NOTES)
    assert listing.has_unfiled is True


def test_has_unfiled_false_when_all_documents_are_filed(tmp_workspace: Workspace) -> None:
    create_note(tmp_workspace, "filed note", now=datetime(2026, 1, 15, 9, 0))
    listing = list_months(tmp_workspace, NOTES)
    assert listing.has_unfiled is False
