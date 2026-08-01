"""The Links pane, shared by both preview surfaces.

The full-screen preview and the list screen's preview pane show the same thing:
what this record points at, above what points at it. The rows are built here so
the two cannot drift -- a link that renders one way in one surface and another
way in the other is a bug waiting to be reported.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from textual.widgets import Label, ListItem

from endpaper.core.links import inbound_links, outbound_links, resolve_id, resolve_link
from endpaper.core.models import Link, LinkStatus, LinkTarget, Workspace
from endpaper.tui.rendering import NO_INBOUND_LINKS, NO_OUTBOUND_LINKS, render_link_row


class LinkRow(ListItem):
    """One row in the Links pane. `direction` is `"out"` or `"in"`.

    `target` is the *other* record involved: for an outbound row, the link's
    resolved destination (None when dead -- opening it reports rather than
    navigating, US7 AC5); for an inbound row, the record the link was found
    in (see `describe_link_source`), since the link's own destination is
    trivially the record already being previewed.
    """

    def __init__(
        self, link: Link, status: LinkStatus, target: LinkTarget | None, *, direction: str
    ) -> None:
        super().__init__(Label(render_link_row(link, status, target, direction=direction)))
        self.link = link
        self.status = status
        self.target = target
        self.direction = direction


class MessageRow(ListItem):
    """A non-selectable informational row: a section heading, or 'nothing points
    here'. Not a LinkRow, so the open action skips it."""

    def __init__(self, text: str) -> None:
        super().__init__(Label(text))


def describe_link_source(workspace: Workspace, link: Link) -> LinkTarget:
    """The record an *inbound* link comes from.

    Resolving an inbound link the ordinary way returns the record already being
    previewed, which is useless for both display and navigation -- the link
    points *here* by definition. What a reader wants is where it came from.

    Falls back to the source file's own path and stem when the containing file
    is not itself a record endpaper can resolve, so a row always renders.
    """
    tasks_file = workspace.tasks_file
    if link.source == tasks_file:
        return LinkTarget(
            id="", path=tasks_file, title=link.text or tasks_file.name, kind="task", line=link.line
        )

    document_id = _document_id_at(workspace, link.source)
    if document_id is not None:
        target, _warnings = resolve_id(workspace, document_id)
        if target is not None:
            return target

    kind: Literal["meeting", "note"] = (
        "meeting" if _under(link.source, workspace.meetings_dir) else "note"
    )
    return LinkTarget(id="", path=link.source, title=link.source.stem, kind=kind, line=None)


def _under(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _document_id_at(workspace: Workspace, path: Path) -> str | None:
    from endpaper.core.documents import _read_document

    document = _read_document(path)
    return document.id if document is not None else None


def build_link_rows(
    workspace: Workspace, source: Path, document_id: str | None, inbound: tuple[Link, ...]
) -> list[ListItem]:
    """Every row of the Links pane for one record: outbound above, inbound below.

    `inbound` is passed in rather than fetched, because it costs a workspace scan
    and each surface decides for itself when to pay for it (FR-049). Outbound
    links come from the record already on screen and are cheap enough to compute
    here.

    Never raises.
    """
    rows: list[ListItem] = [MessageRow("Points at")]

    outbound = outbound_links(workspace, source)
    if not outbound:
        rows.append(MessageRow(f"  {NO_OUTBOUND_LINKS}"))
    else:
        for link, _status in outbound:
            target, status = resolve_link(workspace, link)
            rows.append(LinkRow(link, status, target, direction="out"))

    rows.append(MessageRow(""))
    rows.append(MessageRow("Points here"))

    if not inbound:
        rows.append(MessageRow(f"  {NO_INBOUND_LINKS}"))
    else:
        for link in inbound:
            source_target = describe_link_source(workspace, link)
            rows.append(LinkRow(link, "resolved", source_target, direction="in"))

    return rows


def fetch_inbound(workspace: Workspace, document_id: str | None) -> tuple[Link, ...]:
    """Inbound links for a record, or () when it has no id to be pointed at."""
    if document_id is None:
        return ()
    return inbound_links(workspace, document_id)
