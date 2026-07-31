from __future__ import annotations

import json
import sys
from collections.abc import Iterable

from endpaper.core.models import Document, Task, Workspace


def relative_path(workspace: Workspace, document: Document) -> str:
    return document.path.relative_to(workspace.root).as_posix()


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


def _task_record(task: Task) -> dict[str, object]:
    return {
        "id": task.id,
        "text": task.text,
        "done": task.done,
        "type": task.type,
        "tags": list(task.tags),
        "created": task.created.isoformat() if task.created else None,
        "line": task.line,
        "body": task.body,
    }


def print_tasks_json(tasks: Iterable[Task]) -> None:
    print(json.dumps([_task_record(task) for task in tasks], ensure_ascii=False))


def print_task_show(task: Task) -> None:
    """Human form of `task show`: the same columns `task list` prints for one
    task, then its body verbatim after a blank line. A task with no body prints
    the summary line alone (contracts/cli.md)."""
    print_task_line(task)
    if task.body:
        print()
        print(task.body)


def print_task_show_json(task: Task) -> None:
    """JSON form of `task show`: one object, identical in shape to an entry of
    `task list --json`."""
    print(json.dumps(_task_record(task), ensure_ascii=False))
