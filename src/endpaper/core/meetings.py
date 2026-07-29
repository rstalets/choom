from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime

from endpaper.core.documents import (
    create_document,
    filter_documents,
    match_document,
    scan_documents,
)
from endpaper.core.models import Collection, Document, DocumentFilter, ScanWarning, Workspace

MEETINGS = Collection("m_", "meetings", ("meetings",), frozenset())


def create_meeting(
    workspace: Workspace,
    description: str,
    *,
    type: str = "",
    tags: Sequence[str] = (),
    now: datetime | None = None,
) -> Document:
    return create_document(workspace, MEETINGS, description, type=type, tags=tags, now=now)


def scan_meetings(workspace: Workspace) -> tuple[list[Document], list[ScanWarning]]:
    return scan_documents(workspace, MEETINGS)


def filter_meetings(meetings: Iterable[Document], f: DocumentFilter) -> list[Document]:
    return filter_documents(meetings, f)


def match_meeting(meeting: Document, query: str) -> bool:
    return match_document(meeting, query)
