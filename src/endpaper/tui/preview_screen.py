from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Markdown

from endpaper.core.documents import _read_document
from endpaper.core.links import inbound_links, outbound_links, resolve_link
from endpaper.core.models import Document, Link, LinkStatus, LinkTarget, Workspace
from endpaper.tui.rendering import (
    NO_INBOUND_LINKS,
    NO_OUTBOUND_LINKS,
    render_link_row,
    render_preview_markdown,
)
from endpaper.tui.status_bar import LINKS_SECTION_HELP, PREVIEW_HELP, StatusBar


class LinkRow(ListItem):
    """One row in the Links section. `direction` is `"out"` or `"in"`.

    `target` is the *other* record involved: for an outbound row, the link's
    resolved destination (None when dead -- opening it reports rather than
    navigating, US7 AC5); for an inbound row, the record the link was found
    in (see `_describe_link_source`), since the link's own destination is
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


class _MessageRow(ListItem):
    """A non-selectable informational row: a section heading or 'nothing
    points here'. Not a LinkRow, so `action_open_link` skips it."""

    def __init__(self, text: str) -> None:
        super().__init__(Label(text))


def _links_workspace(app: object) -> Workspace:
    workspace: Workspace = app.workspace  # type: ignore[attr-defined]
    return workspace


def _describe_link_source(workspace: Workspace, link: Link) -> LinkTarget:
    """The record an *inbound* link comes from, for display and for `enter`/`o`
    to navigate to. Unlike an outbound link's `resolve_link` target (which for
    an inbound link is trivially the record already being previewed), this
    describes the *other* end -- the file that contains the link."""
    if link.in_tasks_field:
        return LinkTarget(id="", path=link.source, title=link.text, kind="task", line=link.line)

    document = _read_document(link.source)
    title = document.title if document is not None else link.source.name
    try:
        link.source.relative_to(workspace.meetings_dir)
        kind: str = "meeting"
    except ValueError:
        kind = "note"
    return LinkTarget(
        id=document.id if document is not None else "",
        path=link.source,
        title=title,
        kind=kind,  # type: ignore[arg-type]
        line=None,
    )


class PreviewScreen(Screen[None]):
    BINDINGS = [
        Binding("e", "edit", "Edit", show=True),
        Binding("b", "toggle_links", "Backlinks", show=True),
        Binding("escape", "close_preview", "Back", show=True),
        Binding("j", "links_cursor_down", "Down", show=False),
        Binding("k", "links_cursor_up", "Up", show=False),
        # No "enter" binding here: ListView itself binds "enter" (to post
        # Selected) and, focused, takes priority over a screen-level binding
        # for the same key -- so opening a link on enter is wired via the
        # Selected message handler below instead. "o" is a plain alias since
        # ListView does not claim it.
        Binding("o", "open_link", "Open", show=False),
    ]

    def __init__(self, path: Path, document: Document | None, *, note: str | None = None) -> None:
        super().__init__()
        self.path = path
        self.document = document
        self._note = note
        self._resumed_once = False
        self._links_expanded = False
        #: Inbound links cost a workspace scan (FR-049), so they are fetched
        #: once, the first time the section is expanded, and reused on every
        #: later toggle -- reset only when the document itself is re-read.
        self._inbound_cache: tuple[Link, ...] | None = None

    @property
    def meeting(self) -> Document | None:
        """Feature 001 compatibility alias for `document`."""
        return self.document

    def compose(self) -> ComposeResult:
        yield Markdown(id="full-preview")
        with Vertical(id="links-section"):
            yield ListView(id="links-list")
        with Vertical(id="bottom-bar"):
            yield StatusBar(PREVIEW_HELP, id="status-bar")

    def on_mount(self) -> None:
        self._update_content()
        self.query_one("#links-section").display = False
        if self._note:
            self.query_one(StatusBar).update(f"⚠ {self._note}   {PREVIEW_HELP}")

    async def on_screen_resume(self) -> None:
        # `ScreenResume` also fires once at the initial push, coincident with
        # `on_mount`; only re-render on a genuine return to this screen (e.g.
        # popping back from EditScreen after a save), FR-007.
        if not self._resumed_once:
            self._resumed_once = True
            return
        self.document = _read_document(self.path)
        self._update_content()
        self._links_expanded = False
        self._inbound_cache = None
        self.query_one("#links-section").display = False
        self._render_status()

    def _update_content(self) -> None:
        self.query_one("#full-preview", Markdown).update(
            render_preview_markdown(self.path, self.document)
        )

    def _render_status(self, note: str | None = None) -> None:
        status = self.query_one(StatusBar)
        help_text = LINKS_SECTION_HELP if self._links_expanded else PREVIEW_HELP
        status.update(f"⚠ {note}   {help_text}" if note else help_text)

    def action_edit(self) -> None:
        from endpaper.tui.edit_screen import open_editor

        open_editor(self.app, self.path)

    def action_close_preview(self) -> None:
        if self._links_expanded:
            self._collapse_links()
            return
        self.app.pop_screen()

    # --- Links section (US7) -----------------------------------------------------

    async def action_toggle_links(self) -> None:
        if self._links_expanded:
            self._collapse_links()
        else:
            await self._expand_links()

    async def _expand_links(self) -> None:
        self._links_expanded = True
        self.query_one("#links-section").display = True
        await self._populate_links()
        self.query_one("#links-list", ListView).focus()
        self._render_status()

    def _collapse_links(self) -> None:
        self._links_expanded = False
        self.query_one("#links-section").display = False
        self._render_status()

    def _links_focused(self) -> bool:
        try:
            list_view = self.query_one("#links-list", ListView)
        except NoMatches:
            return False
        return self._links_expanded and list_view.has_focus

    async def _populate_links(self) -> None:
        """Outbound links come from the document already in memory and cost
        nothing; inbound links cost a workspace scan and are fetched only the
        first time the section is expanded (FR-048, FR-049)."""
        list_view = self.query_one("#links-list", ListView)
        await list_view.clear()

        workspace = _links_workspace(self.app)
        rows: list[ListItem] = [_MessageRow("Points at")]

        outbound = outbound_links(workspace, self.path)
        if not outbound:
            rows.append(_MessageRow(f"  {NO_OUTBOUND_LINKS}"))
        else:
            for link, _stale_status in outbound:
                target, status = resolve_link(workspace, link)
                rows.append(LinkRow(link, status, target, direction="out"))

        rows.append(_MessageRow(""))
        rows.append(_MessageRow("Points here"))

        if self._inbound_cache is None:
            self._inbound_cache = (
                inbound_links(workspace, self.document.id) if self.document is not None else ()
            )
        inbound = self._inbound_cache
        if not inbound:
            rows.append(_MessageRow(f"  {NO_INBOUND_LINKS}"))
        else:
            for link in inbound:
                source = _describe_link_source(workspace, link)
                rows.append(LinkRow(link, "resolved", source, direction="in"))

        await list_view.extend(rows)

    def action_links_cursor_down(self) -> None:
        if self._links_focused():
            self.query_one("#links-list", ListView).action_cursor_down()

    def action_links_cursor_up(self) -> None:
        if self._links_focused():
            self.query_one("#links-list", ListView).action_cursor_up()

    @on(ListView.Selected, "#links-list")
    def _on_link_selected(self, event: ListView.Selected) -> None:
        self.action_open_link()

    def action_open_link(self) -> None:
        if not self._links_expanded:
            return
        list_view = self.query_one("#links-list", ListView)
        row = list_view.highlighted_child
        if not isinstance(row, LinkRow):
            return

        if row.target is None:
            unresolved = row.link.target_id or row.link.path or "?"
            self._render_status(f"link to {unresolved!r} does not resolve")
            return

        target = row.target
        if target.kind == "task":
            from endpaper.tui.edit_screen import open_editor

            open_editor(self.app, target.path)
            return

        document = _read_document(target.path)
        self.app.push_screen(PreviewScreen(target.path, document))
