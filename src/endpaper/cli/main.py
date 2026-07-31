from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from endpaper import __version__
from endpaper.cli.output import (
    print_documents_json,
    print_documents_table,
    print_error,
    print_tasks_json,
    print_tasks_table,
    relative_path,
)
from endpaper.core.documents import filter_documents
from endpaper.core.errors import EndpaperError, UsageError, WorkspaceError
from endpaper.core.meetings import create_meeting, scan_meetings
from endpaper.core.models import DocumentFilter, TaskFilter
from endpaper.core.notes import create_note, open_daily_note, scan_notes
from endpaper.core.tasks import add_task, filter_tasks, load_tasks, set_task_state
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

    note_parser = subparsers.add_parser("note", help="create or list notes")
    note_subparsers = note_parser.add_subparsers(dest="note_command", required=True)

    note_subparsers.add_parser("today", help="open (creating if needed) today's daily note")

    note_new_parser = note_subparsers.add_parser(
        "new",
        help="create a note",
        description=(
            "Create a note. NOTE: '#' starts a comment in bash and zsh, so an unquoted "
            "#tag is silently stripped by the shell before endpaper ever sees it. Use --tag "
            "instead, or put the #tag inside a quoted description."
        ),
    )
    note_new_parser.add_argument("description")
    note_new_parser.add_argument("--type", default="")
    note_new_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="repeatable; the supported way to attach a tag on the command line",
    )

    note_list_parser = note_subparsers.add_parser("list", help="list notes")
    note_list_parser.add_argument("--json", action="store_true")
    note_list_parser.add_argument("--type")
    note_list_parser.add_argument("--tag", action="append", default=[])
    note_list_parser.add_argument("--since", help="ISO date, e.g. 2026-07-28; inclusive")

    task_parser = subparsers.add_parser("task", help="capture, list, and complete tasks")
    task_subparsers = task_parser.add_subparsers(dest="task_command", required=True)

    task_add_parser = task_subparsers.add_parser(
        "add",
        help="capture a task",
        description=(
            "Capture a task. NOTE: '#' starts a comment in bash and zsh, so an unquoted "
            "#tag is silently stripped by the shell before endpaper ever sees it. Use --tag "
            "instead, or put the #tag inside a quoted description."
        ),
    )
    task_add_parser.add_argument("description")
    task_add_parser.add_argument("--type", default="")
    task_add_parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="repeatable; the supported way to attach a tag on the command line",
    )

    task_list_parser = task_subparsers.add_parser("list", help="list tasks")
    task_list_parser.add_argument("--json", action="store_true")
    task_list_parser.add_argument("--all", action="store_true", help="include completed tasks")
    task_list_parser.add_argument(
        "--done", action="store_true", help="completed tasks only; wins over --all"
    )
    task_list_parser.add_argument("--type")
    task_list_parser.add_argument("--tag", action="append", default=[])

    task_done_parser = task_subparsers.add_parser("done", help="mark a task complete")
    task_done_parser.add_argument("id")

    task_undone_parser = task_subparsers.add_parser("undone", help="mark a task incomplete")
    task_undone_parser.add_argument("id")

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


_GUIDANCE_ADVICE = {
    "AGENTS.md": "Add the commands and file format an assistant needs.",
    "CLAUDE.md": "Add a line telling your assistant to read AGENTS.md.",
}


def _cmd_init() -> int:
    result = init_workspace(Path.cwd())
    print(str(result.workspace.root))
    for name in result.skipped:
        print(
            f"note: {name} already exists and was left unchanged.\n      {_GUIDANCE_ADVICE[name]}",
            file=sys.stderr,
        )
    return 0


def _parse_since(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise UsageError(f"--since expects a date like 2026-07-28, got {value!r}") from None


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

    document_filter = DocumentFilter(
        type=namespace.type,
        tags=tuple(namespace.tag),
        since=_parse_since(namespace.since),
    )
    filtered = filter_documents(meetings, document_filter)

    if namespace.json:
        print_documents_json(workspace, filtered)
    else:
        print_documents_table(workspace, filtered)
    return 0


def _cmd_note_today() -> int:
    workspace = find_workspace(Path.cwd())
    daily = open_daily_note(workspace)
    print(daily.path.relative_to(workspace.root).as_posix())
    return 0


def _cmd_note_new(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())
    note = create_note(
        workspace,
        namespace.description,
        type=namespace.type,
        tags=tuple(namespace.tag),
    )
    print(relative_path(workspace, note))
    return 0


def _cmd_note_list(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())
    notes, warnings = scan_notes(workspace)
    for warning in warnings:
        print_error(warning.message)

    document_filter = DocumentFilter(
        type=namespace.type,
        tags=tuple(namespace.tag),
        since=_parse_since(namespace.since),
    )
    filtered = filter_documents(notes, document_filter)

    if namespace.json:
        print_documents_json(workspace, filtered)
    else:
        print_documents_table(workspace, filtered)
    return 0


def _cmd_task_add(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())
    task = add_task(
        workspace,
        namespace.description,
        type=namespace.type,
        tags=tuple(namespace.tag),
    )
    print(task.id)
    return 0


def _cmd_task_list(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())
    tasks, warnings = load_tasks(workspace)
    for warning in warnings:
        print_error(warning.message)

    task_filter = TaskFilter(
        type=namespace.type,
        tags=tuple(namespace.tag),
        include_done=namespace.all,
        only_done=namespace.done,
    )
    filtered = filter_tasks(tasks, task_filter)

    if namespace.json:
        print_tasks_json(filtered)
    else:
        print_tasks_table(filtered)
    return 0


def _cmd_task_done(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())
    set_task_state(workspace, namespace.id, done=True)
    return 0


def _cmd_task_undone(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())
    set_task_state(workspace, namespace.id, done=False)
    return 0


def _dispatch(namespace: argparse.Namespace) -> int:
    if namespace.command == "init":
        return _cmd_init()
    if namespace.command == "meeting":
        if namespace.meeting_command == "new":
            return _cmd_meeting_new(namespace)
        return _cmd_meeting_list(namespace)
    if namespace.command == "note":
        if namespace.note_command == "today":
            return _cmd_note_today()
        if namespace.note_command == "new":
            return _cmd_note_new(namespace)
        return _cmd_note_list(namespace)
    if namespace.command == "task":
        if namespace.task_command == "add":
            return _cmd_task_add(namespace)
        if namespace.task_command == "done":
            return _cmd_task_done(namespace)
        if namespace.task_command == "undone":
            return _cmd_task_undone(namespace)
        return _cmd_task_list(namespace)
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
