from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

from endpaper.core.models import Document, LinkDirection, LinkReport, Task, Workspace


def relative_path(workspace: Workspace, document: Document) -> str:
    return document.path.relative_to(workspace.root).as_posix()


def _relative(workspace: Workspace, path: Path) -> str:
    try:
        return path.relative_to(workspace.root).as_posix()
    except ValueError:
        return path.as_posix()


def print_document_line(workspace: Workspace, document: Document) -> None:
    print(
        "\t".join(
            [
                document.created[:10],
                document.type,
                document.title,
                ",".join(document.tags),
            ]
        )
    )


def print_documents_table(workspace: Workspace, documents: Iterable[Document]) -> None:
    for document in documents:
        print_document_line(workspace, document)


def print_documents_json(workspace: Workspace, documents: Iterable[Document]) -> None:
    records = [
        {
            "id": document.id,
            "path": relative_path(workspace, document),
            "title": document.title,
            "type": document.type,
            "tags": list(document.tags),
            "created": document.created,
            "updated": document.updated,
        }
        for document in documents
    ]
    print(json.dumps(records, ensure_ascii=False))


def print_error(message: str) -> None:
    print(f"endpaper: {message}", file=sys.stderr)


def print_task_line(task: Task) -> None:
    print(
        "\t".join(
            [
                task.id or "",
                "done" if task.done else "open",
                task.created.isoformat() if task.created else "-",
                task.type,
                task.text,
                ",".join(task.tags),
            ]
        )
    )


def print_tasks_table(tasks: Iterable[Task]) -> None:
    for task in tasks:
        print_task_line(task)


def print_tasks_json(tasks: Iterable[Task]) -> None:
    records = [
        {
            "id": task.id,
            "text": task.text,
            "done": task.done,
            "type": task.type,
            "tags": list(task.tags),
            "created": task.created.isoformat() if task.created else None,
            "line": task.line,
        }
        for task in tasks
    ]
    print(json.dumps(records, ensure_ascii=False))


def _link_report_line(workspace: Workspace, report: LinkReport) -> str:
    return "\t".join(
        [
            f"{_relative(workspace, report.file)}:{report.line}",
            report.status,
            report.target_id or "",
            report.text,
        ]
    )


def _link_report_dict(workspace: Workspace, report: LinkReport) -> dict[str, object]:
    return {
        "file": _relative(workspace, report.file),
        "line": report.line,
        "text": report.text,
        "target_id": report.target_id,
        "old_path": report.old_path,
        "new_path": report.new_path,
        "status": report.status,
    }


def print_link_reports_table(workspace: Workspace, reports: Iterable[LinkReport]) -> None:
    """Tab-separated, one row per link, no header -- matching `task list` and
    `meeting list` so `cut -f` works. Shared by `links <id>`, `links check`, and
    `links heal`, since they all report the same shape."""
    for report in reports:
        print(_link_report_line(workspace, report))


def print_link_reports_json(workspace: Workspace, reports: Iterable[LinkReport]) -> None:
    """The array form used by `links check` and `links heal`."""
    print(json.dumps([_link_report_dict(workspace, r) for r in reports], ensure_ascii=False))


def print_links_table(
    workspace: Workspace, outbound: Iterable[LinkReport], inbound: Iterable[LinkReport]
) -> None:
    for report in outbound:
        print(_link_report_line(workspace, report))
    for report in inbound:
        print(_link_report_line(workspace, report))


def print_links_json(
    workspace: Workspace,
    target_id: str,
    outbound: Iterable[LinkReport],
    inbound: Iterable[LinkReport],
    *,
    direction: LinkDirection,
) -> None:
    """`links <id> --json`: the direction-grouped object when `direction` is
    `both`; the bare array -- the same shape `check`/`heal` use -- otherwise."""
    if direction == "both":
        print(
            json.dumps(
                {
                    "id": target_id,
                    "out": [_link_report_dict(workspace, r) for r in outbound],
                    "in": [_link_report_dict(workspace, r) for r in inbound],
                },
                ensure_ascii=False,
            )
        )
    elif direction == "out":
        print(json.dumps([_link_report_dict(workspace, r) for r in outbound], ensure_ascii=False))
    else:
        print(json.dumps([_link_report_dict(workspace, r) for r in inbound], ensure_ascii=False))
