from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from endpaper.core.errors import WorkspaceError
from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.core.notes import create_note, open_daily_note
from endpaper.core.workspace import find_workspace, init_workspace


def generate(workspace_root: Path, count: int) -> Workspace:
    try:
        workspace = find_workspace(workspace_root)
    except WorkspaceError:
        workspace = init_workspace(workspace_root).workspace

    base = datetime(2026, 1, 1, 9, 0, 0)
    for i in range(count):
        when = base + timedelta(minutes=i)
        create_meeting(
            workspace,
            f"generated meeting {i}",
            type="standup" if i % 3 == 0 else "",
            tags=("perf",) if i % 5 == 0 else (),
            now=when,
        )
    return workspace


def generate_notes(workspace_root: Path, count: int) -> Workspace:
    try:
        workspace = find_workspace(workspace_root)
    except WorkspaceError:
        workspace = init_workspace(workspace_root).workspace

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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an N-meeting, N-note workspace for perf tests."
    )
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--path", type=Path, default=Path.cwd())
    args = parser.parse_args()
    workspace = generate(args.path, args.count)
    generate_notes(workspace.root, args.count)
    print(f"generated {args.count} meetings and {args.count} notes in {workspace.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
