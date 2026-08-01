"""Delete a record by id -- the one entry point both front-ends call.

The TUI has a path in hand for a highlighted document and could unlink it
directly; that is exactly the divergence Principle I exists to prevent. Going
through `resolve_id` here means the ambiguity check and the wrong-collection
check (`expect`) run for every caller, not just the CLI (research R1, R4).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from choom.core.documents import delete_document
from choom.core.errors import NotFoundError, UsageError
from choom.core.links import resolve_id
from choom.core.models import Workspace
from choom.core.tasks import delete_task


@dataclass(frozen=True, slots=True)
class Deleted:
    """What `delete_by_id` removed, so a caller can report it without
    re-reading. Nothing persists it (data-model.md §1)."""

    id: str
    kind: str
    title: str
    path: Path


def delete_by_id(workspace: Workspace, record_id: str, *, expect: str | None = None) -> Deleted:
    """Resolve `record_id` to a record and delete it.

    `expect`, when given, is one of `"meeting"`, `"note"`, or `"task"` -- the
    caller's guard against deleting a record of the wrong kind (e.g. `choom
    meeting delete <note-id>`).

    Raises:
        NotFoundError: no record carries `record_id`, or `expect` is given and
            the record it resolves to is a different kind. Either way, the
            message names the id and the kind that was expected.
        UsageError: more than one record carries `record_id`; names every
            conflicting path.
        WorkspaceError: the file, or `tasks.md`, could not be written.
    """
    target, warnings = resolve_id(workspace, record_id)

    ambiguous = next((w for w in warnings if w.reason == "link_ambiguous"), None)
    if ambiguous is not None:
        raise UsageError(ambiguous.message)

    if target is None:
        kind_word = expect or "record"
        raise NotFoundError(f"no {kind_word} with id {record_id!r}")

    if expect is not None and target.kind != expect:
        raise NotFoundError(f"no {expect} with id {record_id!r}")

    if target.kind == "task":
        task = delete_task(workspace, record_id)
        return Deleted(id=record_id, kind="task", title=task.text, path=workspace.tasks_file)

    delete_document(target.path)
    return Deleted(id=record_id, kind=target.kind, title=target.title, path=target.path)
