from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

from choom.core.errors import WorkspaceError
from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.notes import create_note, open_daily_note
from choom.core.workspace import find_workspace, init_workspace


def _months_before(base: date, n: int) -> tuple[int, int]:
    month = base.month - n
    year = base.year
    while month <= 0:
        month += 12
        year -= 1
    return year, month


def _spread_datetimes(
    now: datetime, count: int, spread_months: int, current_month_count: int
) -> list[datetime]:
    """`current_month_count` documents dated in `now`'s month, the rest spread evenly
    across the `spread_months - 1` months before it -- so a month-scoped read of the
    current month sees a known, small subset rather than the whole fixture."""
    current_count = min(current_month_count, count)
    remaining = count - current_count
    earlier_months = max(spread_months - 1, 1)
    per_month, extra = divmod(remaining, earlier_months)

    when: list[datetime] = []
    for m in range(1, earlier_months + 1):
        year, month = _months_before(now.date(), m)
        this_month_count = per_month + (1 if m <= extra else 0)
        for i in range(this_month_count):
            when.append(datetime(year, month, 15, 9, 0) + timedelta(minutes=i))

    current_base = now.replace(hour=9, minute=0, second=0, microsecond=0)
    for i in range(current_count):
        when.append(current_base + timedelta(minutes=i))

    return when


def generate(
    workspace_root: Path,
    count: int,
    *,
    spread_months: int = 1,
    current_month_count: int = 5,
    now: datetime | None = None,
) -> Workspace:
    try:
        workspace = find_workspace(workspace_root)
    except WorkspaceError:
        workspace = init_workspace(workspace_root).workspace

    if spread_months <= 1:
        base = datetime(2026, 1, 1, 9, 0, 0)
        dates = [base + timedelta(minutes=i) for i in range(count)]
    else:
        dates = _spread_datetimes(now or datetime.now(), count, spread_months, current_month_count)

    for i, when in enumerate(dates):
        create_meeting(
            workspace,
            f"generated meeting {i}",
            type="standup" if i % 3 == 0 else "",
            tags=("perf",) if i % 5 == 0 else (),
            now=when,
        )
    return workspace


def generate_notes(
    workspace_root: Path,
    count: int,
    *,
    spread_months: int = 1,
    current_month_count: int = 5,
    now: datetime | None = None,
) -> Workspace:
    try:
        workspace = find_workspace(workspace_root)
    except WorkspaceError:
        workspace = init_workspace(workspace_root).workspace

    if spread_months <= 1:
        base = datetime(2026, 1, 1, 9, 0, 0)
        daily_count = min(count, 30)
        for i in range(daily_count):
            open_daily_note(workspace, now=base + timedelta(days=i))

        for i in range(count - daily_count):
            when = base + timedelta(minutes=i)
            create_note(
                workspace,
                f"generated note {i}",
                type="research" if i % 3 == 0 else "",
                tags=("perf",) if i % 5 == 0 else (),
                now=when,
            )
        return workspace

    dates = _spread_datetimes(now or datetime.now(), count, spread_months, current_month_count)
    for i, when in enumerate(dates):
        create_note(
            workspace,
            f"generated note {i}",
            type="research" if i % 3 == 0 else "",
            tags=("perf",) if i % 5 == 0 else (),
            now=when,
        )
    return workspace


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an N-meeting, N-note workspace for perf tests."
    )
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--path", type=Path, default=Path.cwd())
    parser.add_argument(
        "--spread-months",
        type=int,
        default=1,
        help="spread documents across this many months (most in earlier months, a few in "
        "the current month) instead of all in 2026-01",
    )
    args = parser.parse_args()
    workspace = generate(args.path, args.count, spread_months=args.spread_months)
    generate_notes(workspace.root, args.count, spread_months=args.spread_months)
    print(f"generated {args.count} meetings and {args.count} notes in {workspace.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
