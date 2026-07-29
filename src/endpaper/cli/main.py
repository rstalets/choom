from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from endpaper import __version__
from endpaper.cli.output import (
    print_error,
    print_meetings_json,
    print_meetings_table,
    relative_path,
)
from endpaper.core.errors import EndpaperError, UsageError, WorkspaceError
from endpaper.core.meetings import create_meeting, filter_meetings, scan_meetings
from endpaper.core.models import MeetingFilter
from endpaper.core.workspace import find_workspace, init_workspace


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="endpaper",
        description="A corporate-friendly Markdown notes engine that makes your AI happy.",
    )
    parser.add_argument("--version", action="version", version=f"endpaper {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="create a workspace in the current directory")

    meeting_parser = subparsers.add_parser("meeting", help="create or list meetings")
    meeting_subparsers = meeting_parser.add_subparsers(dest="meeting_command", required=True)

    new_parser = meeting_subparsers.add_parser(
        "new",
        help="create a meeting",
        description=(
            "Create a meeting. NOTE: '#' starts a comment in bash and zsh, so an unquoted "
            "#tag is silently stripped by the shell before endpaper ever sees it. Use --tag "
            "instead, or put the #tag inside a quoted description."
        ),
    )
    new_parser.add_argument("description")
    new_parser.add_argument("--type", default="")
    new_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="repeatable; the supported way to attach a tag on the command line",
    )

    list_parser = meeting_subparsers.add_parser("list", help="list meetings")
    list_parser.add_argument("--json", action="store_true")
    list_parser.add_argument("--type")
    list_parser.add_argument("--tag", action="append", default=[])
    list_parser.add_argument("--since", help="ISO date, e.g. 2026-07-28; inclusive")

    return parser


def _run_tui() -> int:
    if not sys.stdout.isatty():
        print_error("stdout is not a terminal; refusing to open the interface")
        return WorkspaceError.exit_code

    try:
        workspace = find_workspace(Path.cwd())
    except WorkspaceError as exc:
        print_error(str(exc))
        return exc.exit_code

    from endpaper.tui.app import EndpaperApp

    EndpaperApp(workspace).run()
    return 0


def _cmd_init() -> int:
    workspace = init_workspace(Path.cwd())
    print(str(workspace.root))
    return 0


def _cmd_meeting_new(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())
    meeting = create_meeting(
        workspace,
        namespace.description,
        type=namespace.type,
        tags=tuple(namespace.tag),
    )
    print(relative_path(workspace, meeting))
    return 0


def _cmd_meeting_list(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())
    meetings, warnings = scan_meetings(workspace)
    for warning in warnings:
        print_error(warning.message)

    since_date: date | None = None
    if namespace.since:
        try:
            since_date = date.fromisoformat(namespace.since)
        except ValueError:
            raise UsageError(
                f"--since expects a date like 2026-07-28, got {namespace.since!r}"
            ) from None

    meeting_filter = MeetingFilter(
        type=namespace.type,
        tags=tuple(namespace.tag),
        since=since_date,
    )
    filtered = filter_meetings(meetings, meeting_filter)

    if namespace.json:
        print_meetings_json(workspace, filtered)
    else:
        print_meetings_table(workspace, filtered)
    return 0


def _dispatch(namespace: argparse.Namespace) -> int:
    if namespace.command == "init":
        return _cmd_init()
    if namespace.command == "meeting":
        if namespace.meeting_command == "new":
            return _cmd_meeting_new(namespace)
        return _cmd_meeting_list(namespace)
    raise UsageError(f"unknown command: {namespace.command}")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if not args:
        return _run_tui()

    parser = _build_parser()
    try:
        namespace = parser.parse_args(args)
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 0 if code is None else 1

    try:
        return _dispatch(namespace)
    except EndpaperError as exc:
        print_error(str(exc))
        return exc.exit_code
