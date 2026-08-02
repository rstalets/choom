from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from choom import __version__
from choom.cli.output import (
    print_documents_json,
    print_documents_table,
    print_error,
    print_link_reports_json,
    print_link_reports_table,
    print_links_json,
    print_links_table,
    print_task_show,
    print_task_show_json,
    print_tasks_json,
    print_tasks_table,
    relative_path,
)
from choom.core.assistants import resolve_assistant
from choom.core.config import LEGAL_ASSISTANT_VALUES, get_assistant, set_assistant
from choom.core.deletion import delete_by_id
from choom.core.discovery import install_discovery_file
from choom.core.documents import filter_documents
from choom.core.errors import ChoomError, NotFoundError, UsageError, WorkspaceError
from choom.core.links import check_links, heal_links, links_for_id, resolve_id
from choom.core.meetings import create_meeting, scan_meetings
from choom.core.mirrors import propagate_to_documents
from choom.core.models import DocumentFilter, TaskFilter, Workspace
from choom.core.notes import create_note, open_daily_note, scan_notes
from choom.core.tasks import add_task, filter_tasks, get_task, load_tasks, set_task_state
from choom.core.workspace import find_workspace, init_workspace


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="choom",
        description="A corporate-friendly Markdown notes engine that makes your AI happy.",
    )
    parser.add_argument("--version", action="version", version=f"choom {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="create a workspace in the current directory")
    init_parser.add_argument(
        "--assistant",
        choices=LEGAL_ASSISTANT_VALUES,
        default=None,
        help="record which AI assistant /ai calls",
    )

    meeting_parser = subparsers.add_parser("meeting", help="create or list meetings")
    meeting_subparsers = meeting_parser.add_subparsers(dest="meeting_command", required=True)

    new_parser = meeting_subparsers.add_parser(
        "new",
        help="create a meeting",
        description=(
            "Create a meeting. NOTE: '#' starts a comment in bash and zsh, so an unquoted "
            "#tag is silently stripped by the shell before choom ever sees it. Use --tag "
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

    meeting_delete_parser = meeting_subparsers.add_parser(
        "delete", help="delete a meeting (contracts/cli-delete.md)"
    )
    meeting_delete_parser.add_argument("id")
    meeting_delete_parser.add_argument(
        "--force", action="store_true", help="required; deletes without asking"
    )

    note_parser = subparsers.add_parser("note", help="create or list notes")
    note_subparsers = note_parser.add_subparsers(dest="note_command", required=True)

    note_subparsers.add_parser("today", help="open (creating if needed) today's daily note")

    note_new_parser = note_subparsers.add_parser(
        "new",
        help="create a note",
        description=(
            "Create a note. NOTE: '#' starts a comment in bash and zsh, so an unquoted "
            "#tag is silently stripped by the shell before choom ever sees it. Use --tag "
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

    note_delete_parser = note_subparsers.add_parser(
        "delete", help="delete a note (contracts/cli-delete.md)"
    )
    note_delete_parser.add_argument("id")
    note_delete_parser.add_argument(
        "--force", action="store_true", help="required; deletes without asking"
    )

    task_parser = subparsers.add_parser("task", help="capture, list, and complete tasks")
    task_subparsers = task_parser.add_subparsers(dest="task_command", required=True)

    task_add_parser = task_subparsers.add_parser(
        "add",
        help="capture a task",
        description=(
            "Capture a task. NOTE: '#' starts a comment in bash and zsh, so an unquoted "
            "#tag is silently stripped by the shell before choom ever sees it. Use --tag "
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
    task_add_parser.add_argument(
        "--link",
        action="append",
        default=[],
        help="repeatable; record a link to an existing meeting, note, or task id",
    )
    task_add_parser.add_argument("--json", action="store_true")

    task_list_parser = task_subparsers.add_parser("list", help="list tasks")
    task_list_parser.add_argument("--json", action="store_true")
    task_list_parser.add_argument("--all", action="store_true", help="include completed tasks")
    task_list_parser.add_argument(
        "--done", action="store_true", help="completed tasks only; wins over --all"
    )
    task_list_parser.add_argument("--type")
    task_list_parser.add_argument("--tag", action="append", default=[])

    task_show_parser = task_subparsers.add_parser("show", help="print one task and its body")
    task_show_parser.add_argument("id")
    task_show_parser.add_argument("--json", action="store_true")

    task_done_parser = task_subparsers.add_parser("done", help="mark a task complete")
    task_done_parser.add_argument("id")
    task_done_parser.add_argument("--json", action="store_true")

    task_undone_parser = task_subparsers.add_parser("undone", help="mark a task incomplete")
    task_undone_parser.add_argument("id")
    task_undone_parser.add_argument("--json", action="store_true")

    task_delete_parser = task_subparsers.add_parser(
        "delete", help="delete a task (contracts/cli-delete.md)"
    )
    task_delete_parser.add_argument("id")
    task_delete_parser.add_argument(
        "--force", action="store_true", help="required; deletes without asking"
    )

    config_parser = subparsers.add_parser("config", help="get or set workspace settings")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)

    config_assistant_parser = config_subparsers.add_parser(
        "assistant", help="get or set which AI assistant /ai calls"
    )
    config_assistant_parser.add_argument(
        "value", nargs="?", default=None, choices=LEGAL_ASSISTANT_VALUES
    )
    config_assistant_parser.add_argument("--json", action="store_true")

    links_parser = subparsers.add_parser(
        "links",
        help="ask what points at a record, or audit and repair links",
        description=(
            "choom links <id> [--json] [--direction out|in|both]\n"
            "choom links check [<path>...] [--json]\n"
            "choom links heal  [<path>...] [--json] [--dry-run]\n\n"
            "'check' and 'heal' are reserved words in the <id> position; every real id "
            "carries a collection prefix (meeting_/note_/task_), so this is never ambiguous."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    links_parser.add_argument("target", help="a record id, or 'check'/'heal'")
    links_parser.add_argument(
        "paths", nargs="*", help="check/heal only: limit to these workspace-relative paths"
    )
    links_parser.add_argument("--json", action="store_true")
    links_parser.add_argument(
        "--direction", choices=["out", "in", "both"], default="both", help="links <id> only"
    )
    links_parser.add_argument(
        "--dry-run", action="store_true", help="heal only: report without writing"
    )

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

    from choom.tui.app import ChoomApp

    ChoomApp(workspace).run()
    return 0


_GUIDANCE_ADVICE = {
    "AGENTS.md": "Add the commands and file format an assistant needs.",
    "CLAUDE.md": "Add a line telling your assistant to read AGENTS.md.",
}


def _cmd_init(namespace: argparse.Namespace) -> int:
    result = init_workspace(Path.cwd(), assistant=namespace.assistant)
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


def _cmd_delete(namespace: argparse.Namespace, *, expect: str) -> int:
    """Shared body of `meeting delete`/`note delete`/`task delete`
    (contracts/cli-delete.md): `--force` is a required flag, not a prompt, so
    there is no interactive branch to reach (Principle II). Success prints
    nothing to stdout and returns 0; every failure is a `ChoomError` that
    `main()` already maps to its exit code."""
    workspace = find_workspace(Path.cwd())
    if not namespace.force:
        raise UsageError("refusing to delete without --force")
    delete_by_id(workspace, namespace.id, expect=expect)
    return 0


def _cmd_meeting_delete(namespace: argparse.Namespace) -> int:
    return _cmd_delete(namespace, expect="meeting")


def _cmd_note_delete(namespace: argparse.Namespace) -> int:
    return _cmd_delete(namespace, expect="note")


def _cmd_task_delete(namespace: argparse.Namespace) -> int:
    return _cmd_delete(namespace, expect="task")


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


def _resolve_task_links(workspace: Workspace, raw_ids: list[str]) -> tuple[str, ...]:
    """Every `--link` id, resolved before anything is written (FR-036).

    Raises:
        NotFoundError: an id does not resolve to any record -- exit 1, not 2,
            because the flag was well-formed and names a thing that is not
            there (research R10).
    """
    for target_id in raw_ids:
        target, _warnings = resolve_id(workspace, target_id)
        if target is None:
            raise NotFoundError(f"no record with id {target_id!r}")
    return tuple(raw_ids)


def _cmd_task_add(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())
    links = _resolve_task_links(workspace, namespace.link)
    task = add_task(
        workspace,
        namespace.description,
        type=namespace.type,
        tags=tuple(namespace.tag),
        links=links,
    )
    if namespace.json:
        print_task_show_json(task)
    else:
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


def _cmd_task_show(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())
    task = get_task(workspace, namespace.id)
    if namespace.json:
        print_task_show_json(task)
    else:
        print_task_show(task)
    return 0


def _set_task_state_and_propagate(namespace: argparse.Namespace, *, done: bool) -> int:
    """Shared body of `task done`/`task undone` (contracts/cli.md): tasks.md is
    written first, exactly as before this feature; then every document the
    task links to has its mirrors spliced to the new state. A document failure
    is a warning, never a non-zero exit -- the operation asked for (completing
    or reopening the task) already succeeded, and exiting non-zero would make
    an assistant retry a completion that already happened (research R11)."""
    workspace = find_workspace(Path.cwd())
    task = set_task_state(workspace, namespace.id, done=done)
    documents_updated, warnings = propagate_to_documents(workspace, task)
    for warning in warnings:
        print_error(warning.message)

    if namespace.json:
        print(
            json.dumps(
                {
                    "id": task.id,
                    "done": task.done,
                    "links": list(task.links),
                    "documents_updated": [
                        path.relative_to(workspace.root).as_posix() for path in documents_updated
                    ],
                    "warnings": [w.message for w in warnings],
                },
                ensure_ascii=False,
            )
        )
    return 0


def _cmd_task_done(namespace: argparse.Namespace) -> int:
    return _set_task_state_and_propagate(namespace, done=True)


def _cmd_task_undone(namespace: argparse.Namespace) -> int:
    return _set_task_state_and_propagate(namespace, done=False)


def _cmd_config_assistant(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())

    if namespace.value is not None:
        set_assistant(workspace, namespace.value)
        if namespace.value != "none":
            profile = resolve_assistant(namespace.value).profile
            assert profile is not None  # namespace.value is claude or copilot here
            try:
                install_discovery_file(workspace, profile)
            except WorkspaceError:
                pass
        return 0

    configured = get_assistant(workspace)
    resolved = resolve_assistant(configured)
    resolved_name = resolved.profile.name if resolved.profile is not None else None

    if namespace.json:
        print(
            json.dumps(
                {
                    "configured": configured,
                    "resolved": resolved_name,
                    "source": resolved.source,
                    "available": list(resolved.available),
                },
                ensure_ascii=False,
            )
        )
    else:
        print(f"configured\t{configured or '-'}")
        print(f"resolved\t{resolved_name or '-'}")
        print(f"source\t{resolved.source}")
        print(f"available\t{','.join(resolved.available) or '-'}")
    return 0


def _resolve_link_paths(workspace: Workspace, raw_paths: list[str]) -> tuple[Path, ...]:
    """CLI-supplied path arguments, workspace-relative, to the absolute `Path`s
    `core.links` expects. Pure string arithmetic -- `os.path.normpath` rather than
    `Path.resolve()` so a symlinked tmp dir (macOS) does not make the result
    disagree with `workspace.root`'s own unresolved form."""
    return tuple(Path(os.path.normpath(workspace.root / raw)) for raw in raw_paths)


def _cmd_links_id(workspace: Workspace, namespace: argparse.Namespace) -> int:
    target, outbound, inbound = links_for_id(
        workspace, namespace.target, direction=namespace.direction
    )
    if target is None:
        raise NotFoundError(f"no record with id {namespace.target!r}")

    if namespace.json:
        print_links_json(
            workspace, namespace.target, outbound, inbound, direction=namespace.direction
        )
    else:
        print_links_table(workspace, outbound, inbound)
    return 0


def _cmd_links_check(workspace: Workspace, namespace: argparse.Namespace) -> int:
    paths = _resolve_link_paths(workspace, namespace.paths)
    reports = check_links(workspace, paths)

    if namespace.json:
        print_link_reports_json(workspace, reports)
    else:
        print_link_reports_table(workspace, reports)
    return 1 if reports else 0


def _cmd_links_heal(workspace: Workspace, namespace: argparse.Namespace) -> int:
    paths = _resolve_link_paths(workspace, namespace.paths)
    reports = heal_links(workspace, paths, dry_run=namespace.dry_run)

    if namespace.json:
        print_link_reports_json(workspace, reports)
    else:
        print_link_reports_table(workspace, reports)

    if namespace.dry_run:
        return 1 if reports else 0
    # A real run fixes every stale link, so only a dead one -- never repaired --
    # can still be "remaining" by the time this returns (contracts/cli.md).
    return 1 if any(report.status == "dead" for report in reports) else 0


def _cmd_links(namespace: argparse.Namespace) -> int:
    workspace = find_workspace(Path.cwd())
    if namespace.target == "check":
        return _cmd_links_check(workspace, namespace)
    if namespace.target == "heal":
        return _cmd_links_heal(workspace, namespace)
    return _cmd_links_id(workspace, namespace)


def _dispatch(namespace: argparse.Namespace) -> int:
    if namespace.command == "init":
        return _cmd_init(namespace)
    if namespace.command == "meeting":
        if namespace.meeting_command == "new":
            return _cmd_meeting_new(namespace)
        if namespace.meeting_command == "delete":
            return _cmd_meeting_delete(namespace)
        return _cmd_meeting_list(namespace)
    if namespace.command == "note":
        if namespace.note_command == "today":
            return _cmd_note_today()
        if namespace.note_command == "new":
            return _cmd_note_new(namespace)
        if namespace.note_command == "delete":
            return _cmd_note_delete(namespace)
        return _cmd_note_list(namespace)
    if namespace.command == "task":
        if namespace.task_command == "add":
            return _cmd_task_add(namespace)
        if namespace.task_command == "show":
            return _cmd_task_show(namespace)
        if namespace.task_command == "done":
            return _cmd_task_done(namespace)
        if namespace.task_command == "undone":
            return _cmd_task_undone(namespace)
        if namespace.task_command == "delete":
            return _cmd_task_delete(namespace)
        return _cmd_task_list(namespace)
    if namespace.command == "config":
        return _cmd_config_assistant(namespace)
    if namespace.command == "links":
        return _cmd_links(namespace)
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
    except ChoomError as exc:
        print_error(str(exc))
        return exc.exit_code
