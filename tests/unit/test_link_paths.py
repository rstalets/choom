from __future__ import annotations

from pathlib import Path

import pytest

from endpaper.core.links import relative_destination

WORKSPACE = Path("/tmp/ep-workspace")


@pytest.mark.parametrize(
    ("source", "target", "expected"),
    [
        (
            "meetings/2026/07/a.md",
            "notes/2026/07/b.md",
            "../../../notes/2026/07/b.md",
        ),
        (
            "notes/daily/2026/07/d.md",
            "meetings/2026/07/a.md",
            "../../../../meetings/2026/07/a.md",
        ),
        ("tasks.md", "meetings/2026/07/a.md", "meetings/2026/07/a.md"),
        ("meetings/2026/07/a.md", "tasks.md", "../../../tasks.md"),
        ("notes/stray.md", "notes/daily/2026/07/d.md", "daily/2026/07/d.md"),
        ("meetings/2026/07/a.md", "meetings/2026/07/b.md", "b.md"),
    ],
)
def test_relative_destination_from_every_layout_depth(
    source: str, target: str, expected: str
) -> None:
    dest = relative_destination(WORKSPACE / source, WORKSPACE / target)
    assert dest == expected


def test_forward_slashes_regardless_of_platform() -> None:
    dest = relative_destination(
        WORKSPACE / "notes" / "daily" / "2026" / "07" / "d.md",
        WORKSPACE / "meetings" / "2026" / "07" / "a.md",
    )
    assert "\\" not in dest
    assert dest == "../../../../meetings/2026/07/a.md"


def test_round_trips_back_to_the_target() -> None:
    for source, target in [
        ("meetings/2026/07/a.md", "notes/2026/07/b.md"),
        ("notes/daily/2026/07/d.md", "meetings/2026/07/a.md"),
        ("tasks.md", "meetings/2026/07/a.md"),
        ("meetings/2026/07/a.md", "tasks.md"),
        ("notes/stray.md", "notes/daily/2026/07/d.md"),
        ("meetings/2026/07/a.md", "meetings/2026/07/b.md"),
    ]:
        source_path = WORKSPACE / source
        target_path = WORKSPACE / target
        dest = relative_destination(source_path, target_path)
        resolved = (source_path.parent / dest).resolve()
        assert resolved == target_path.resolve()


def test_worst_case_destination_length_is_well_within_windows_budget() -> None:
    # 117-char worst case measured in research R3 -- this is text in a file, not a
    # filesystem path, so the Windows 260-character budget does not apply to it,
    # but it should stay comfortably small regardless.
    long_name = "2026-07-30-" + "x" * 80 + ".md"
    dest = relative_destination(
        WORKSPACE / "notes" / "daily" / "2026" / "07" / "d.md",
        WORKSPACE / "meetings" / "2026" / "07" / long_name,
    )
    assert len(dest) < 260
