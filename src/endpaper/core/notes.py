from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import datetime

from endpaper.core.documents import _read_document, create_document, scan_documents
from endpaper.core.frontmatter import render_frontmatter
from endpaper.core.models import Collection, DailyNote, Document, ScanWarning, Workspace
from endpaper.core.text import new_document_id

NOTES = Collection("n_", "notes", ("notes", "notes/daily"), frozenset({"daily"}))


def create_note(
    workspace: Workspace,
    description: str,
    *,
    type: str = "",
    tags: Sequence[str] = (),
    now: datetime | None = None,
) -> Document:
    return create_document(workspace, NOTES, description, type=type, tags=tags, now=now)


def scan_notes(workspace: Workspace) -> tuple[list[Document], list[ScanWarning]]:
    return scan_documents(workspace, NOTES)


def open_daily_note(workspace: Workspace, *, now: datetime | None = None) -> DailyNote:
    when = now or datetime.now()
    path = workspace.daily_dir / f"{when:%Y-%m-%d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = when.replace(microsecond=0).isoformat()
    date_str = when.strftime("%Y-%m-%d")
    document = Document(
        id=new_document_id(when.date(), NOTES.id_prefix),
        path=path,
        title=date_str,
        type="daily",
        tags=(),
        created=timestamp,
        updated=timestamp,
    )
    content = render_frontmatter(document)

    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return DailyNote(path=path, document=_read_document(path), created=False)

    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    return DailyNote(path=path, document=document, created=True)
