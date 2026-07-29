from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from endpaper.core.documents import create_document, scan_documents
from endpaper.core.models import Collection, Document, ScanWarning, Workspace

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
