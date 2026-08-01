from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime

from endpaper.core.documents import (
    create_document,
    filter_documents,
    list_months,
    match_document,
    scan_documents,
    scan_month,
)
from endpaper.core.models import (
    Collection,
    Document,
    DocumentFilter,
    MonthListing,
    ScanWarning,
    Workspace,
    YearMonth,
)

MEETINGS = Collection("meeting_", "meetings", ("meetings",), frozenset())


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


def list_meeting_months(workspace: Workspace) -> MonthListing:
    return list_months(workspace, MEETINGS)


def scan_meeting_month(
    workspace: Workspace, month: YearMonth
) -> tuple[list[Document], list[ScanWarning]]:
    return scan_month(workspace, MEETINGS, month)


def filter_meetings(meetings: Iterable[Document], f: DocumentFilter) -> list[Document]:
    return filter_documents(meetings, f)


def match_meeting(meeting: Document, query: str) -> bool:
    return match_document(meeting, query)
