from __future__ import annotations

import threading
from datetime import datetime

from endpaper.core.models import Workspace
from endpaper.core.notes import open_daily_note
from tests.conftest import daily_note_path


def test_first_call_creates_daily_note_with_type_and_iso_title(
    tmp_workspace: Workspace, frozen_now: datetime
) -> None:
    result = open_daily_note(tmp_workspace, now=frozen_now)

    expected_path = daily_note_path(tmp_workspace, frozen_now.date())
    assert result.path == expected_path
    assert result.created is True
    assert result.document is not None
    assert result.document.type == "daily"
    assert result.document.title == "2026-07-28"
    assert result.document.tags == ()
    assert expected_path.is_file()


def test_second_call_same_day_returns_same_path_and_creates_no_second_file(
    tmp_workspace: Workspace, frozen_now: datetime
) -> None:
    first = open_daily_note(tmp_workspace, now=frozen_now)

    daily_dir = tmp_workspace.daily_dir
    files_after_first = sorted(daily_dir.rglob("*.md"))
    assert len(files_after_first) == 1

    second = open_daily_note(tmp_workspace, now=frozen_now)

    assert second.path == first.path
    assert second.created is False
    files_after_second = sorted(daily_dir.rglob("*.md"))
    assert files_after_second == files_after_first


def test_second_call_leaves_file_byte_and_mtime_identical(
    tmp_workspace: Workspace, frozen_now: datetime
) -> None:
    first = open_daily_note(tmp_workspace, now=frozen_now)
    path = first.path

    # Simulate content written by the user in between the two calls.
    path.write_text(path.read_text(encoding="utf-8") + "Some content.\n", encoding="utf-8")
    before_bytes = path.read_bytes()
    before_mtime = path.stat().st_mtime_ns

    open_daily_note(tmp_workspace, now=frozen_now)

    after_bytes = path.read_bytes()
    after_mtime = path.stat().st_mtime_ns
    assert after_bytes == before_bytes
    assert after_mtime == before_mtime


def test_missing_daily_dir_is_recreated(tmp_workspace: Workspace, frozen_now: datetime) -> None:
    import shutil

    shutil.rmtree(tmp_workspace.daily_dir)
    assert not tmp_workspace.daily_dir.exists()

    result = open_daily_note(tmp_workspace, now=frozen_now)

    assert result.created is True
    assert result.path.is_file()


def test_existing_file_with_broken_frontmatter_is_opened_not_replaced_or_repaired(
    tmp_workspace: Workspace, frozen_now: datetime
) -> None:
    path = daily_note_path(tmp_workspace, frozen_now.date())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not frontmatter at all", encoding="utf-8")
    before = path.read_bytes()

    result = open_daily_note(tmp_workspace, now=frozen_now)

    assert result.path == path
    assert result.created is False
    assert result.document is None
    assert path.read_bytes() == before


def test_zero_byte_existing_file_is_treated_as_existing(
    tmp_workspace: Workspace, frozen_now: datetime
) -> None:
    path = daily_note_path(tmp_workspace, frozen_now.date())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    assert path.stat().st_size == 0

    result = open_daily_note(tmp_workspace, now=frozen_now)

    assert result.created is False
    assert result.document is None
    assert path.stat().st_size == 0


def test_no_other_workspace_file_is_modified(
    tmp_workspace: Workspace, frozen_now: datetime
) -> None:
    before = {
        p: p.stat().st_mtime_ns
        for p in tmp_workspace.root.rglob("*")
        if p.is_file() and p != daily_note_path(tmp_workspace, frozen_now.date())
    }

    open_daily_note(tmp_workspace, now=frozen_now)

    for p, mtime in before.items():
        assert p.stat().st_mtime_ns == mtime


def test_cli_note_today_is_idempotent_and_prints_same_relative_path(cli) -> None:
    first = cli("note", "today")
    assert first.exit_code == 0
    assert first.out.startswith("notes/daily/")

    second = cli("note", "today")
    assert second.exit_code == 0
    assert second.out == first.out

    files = list((cli.root / "notes" / "daily").rglob("*.md"))
    assert len(files) == 1


def test_twenty_concurrent_calls_produce_exactly_one_file(
    tmp_workspace: Workspace, frozen_now: datetime
) -> None:
    results: list[object] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def _call() -> None:
        try:
            result = open_daily_note(tmp_workspace, now=frozen_now)
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)
            return
        with lock:
            results.append(result)

    threads = [threading.Thread(target=_call) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(results) == 20
    files = list(tmp_workspace.daily_dir.rglob("*.md"))
    assert len(files) == 1
    created_count = sum(1 for r in results if r.created)  # type: ignore[attr-defined]
    assert created_count == 1
