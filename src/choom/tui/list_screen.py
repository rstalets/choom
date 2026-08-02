from __future__ import annotations

from pathlib import Path
from typing import cast

from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Label, ListItem, ListView, Markdown, Static
from textual.worker import Worker, WorkerCancelled, WorkerFailed

from choom.core.deletion import delete_by_id
from choom.core.documents import _read_document, scan_documents
from choom.core.errors import NotFoundError, UsageError, WorkspaceError
from choom.core.links import resolve_href
from choom.core.models import Document, LinkTarget, ScanWarning, Task, Workspace, YearMonth
from choom.tui.collection_bar import COLLECTIONS, CollectionBar
from choom.tui.columns import (
    TASK_LEAD,
    ColumnLayout,
    column_widths,
    render_header,
    render_row,
)
from choom.tui.command_bar import CommandBar
from choom.tui.confirm_dialog import ConfirmDialog
from choom.tui.edit_screen import EditorPane, EditTarget
from choom.tui.help_screen import HelpScreen
from choom.tui.links_pane import LinkRow, build_link_rows, fetch_inbound
from choom.tui.rendering import render_preview_markdown, render_task_markdown
from choom.tui.scope_pane import CategoryRow, MonthRow, ScopePane, UnfiledRow
from choom.tui.status_bar import (
    EDIT_HELP,
    LIST_HELP,
    TASK_LIST_HELP,
    StatusBar,
    collection_indicator,
)

_EMPTY_STATE = {
    "meetings": "No meetings yet. Press / then 'meeting <description>' to create one.",
    "notes": "No notes yet. Press / then 'note' for today's note, or 'note <description>'.",
    "tasks": "No tasks yet. Press / then 'task <description>' to create one.",
}
_CREATE_VERB = {"meetings": "meeting", "notes": "note"}

#: How often a displayed list re-reads on its own (US2, FR-009). Not the
#: issue's proposed ~10 s: the binding constraint is Textual's main thread,
#: not the disk -- a scoped month read is a few tens of ms even at 200
#: documents, so 2 s spends well under 2% of one core. See research.md R5 for
#: the full frame-budget argument and the trigger to move this read to a
#: worker thread instead of shortening the interval.
REFRESH_SECONDS = 2.0


def _document_key(documents: list[Document]) -> tuple[tuple[object, ...], ...]:
    """The change-detection key for a documents read (research R4): a tuple of
    the fields `DocumentRow._row_text` renders, plus `path` and `updated` so
    an edit that changes no *rendered* field still counts as a change for the
    preview pane. Order is part of the key -- a re-sort with identical rows is
    still a change, since row position is rendered."""
    return tuple(
        (d.id, str(d.path), d.title, d.type, d.tags, d.created, d.updated) for d in documents
    )


def _task_key(tasks: list[Task]) -> tuple[tuple[object, ...], ...]:
    """The change-detection key for a tasks read -- the fields
    `TaskRow._row_text` renders, plus `done` (which changes the row's markup
    but not its text)."""
    return tuple((t.id, t.text, t.type, t.tags, t.done, t.created) for t in tasks)


def _empty_state_message(app: object) -> str:
    active = app.active  # type: ignore[attr-defined]
    if active == "tasks":
        return _EMPTY_STATE["tasks"]

    if app.filter_query:  # type: ignore[attr-defined]
        return f"No matches for '{app.filter_query}'."  # type: ignore[attr-defined]

    listing = app.list_scope(active)  # type: ignore[attr-defined]
    if len(listing.months) <= 1 and not listing.has_unfiled:
        return _EMPTY_STATE[active]

    selection = app.scope_selection.get(active)  # type: ignore[attr-defined]
    if selection == "unfiled":
        return f"No unfiled {active}."
    month = selection if isinstance(selection, YearMonth) else app.month_scope[active]  # type: ignore[attr-defined]
    verb = _CREATE_VERB[active]
    return f"No {active} in {month}. Press / then '{verb} <description>' to create one."


class DocumentRow(ListItem):
    def __init__(self, document: Document, layout: ColumnLayout) -> None:
        super().__init__(Label(self._row_text(document, layout)))
        self.document = document

    @property
    def meeting(self) -> Document:
        """Feature 001 compatibility alias for `document`."""
        return self.document

    @staticmethod
    def _row_text(document: Document, layout: ColumnLayout) -> str:
        cells = (document.created[:10], document.type, document.title, ",".join(document.tags))
        return render_row(cells, layout)

    def update_layout(self, layout: ColumnLayout) -> None:
        """Re-render this row's text for a new column layout (a resize),
        without re-reading anything -- `self.document` is already in hand."""
        self.query_one(Label).update(self._row_text(self.document, layout))


MeetingRow = DocumentRow  # alias, feature 001 compatibility


class TaskRow(ListItem):
    def __init__(self, task: Task, layout: ColumnLayout) -> None:
        super().__init__(Label(self._row_text(task, layout)))
        self.record = task

    @staticmethod
    def _row_text(task: Task, layout: ColumnLayout) -> str:
        # The done marker sits outside the four labelled columns (spec
        # Assumptions): the four columns mean the same four fields in every
        # collection, and folding the marker into the date column would make
        # that column mean two different things depending on the collection.
        # The brackets are escaped (`\[` not `[`) because Label content is
        # parsed as Rich console markup: an unescaped "[x]" opens a style tag
        # named "x" that Rich silently drops from the rendered text, which
        # would make the done marker invisible on every completed task.
        marker = "\\[x]" if task.done else "\\[ ]"  # 3 visible chars + the space below = TASK_LEAD
        cells = (
            task.created.isoformat() if task.created else "",
            task.type,
            task.text,
            ",".join(task.tags),
        )
        text = f"{marker} {render_row(cells, layout)}"
        return f"[strike]{text}[/strike]" if task.done else text

    def update_layout(self, layout: ColumnLayout) -> None:
        """Re-render this row's text for a new column layout (a resize),
        without re-reading anything -- `self.record` is already in hand."""
        self.query_one(Label).update(self._row_text(self.record, layout))


class ListScreen(Screen[None]):
    BINDINGS = [
        Binding("tab", "next_collection", "Collection", show=True),
        Binding("shift+tab", "previous_collection", "Collection", show=False),
        Binding("j", "cursor_down", "Down", show=True),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("h", "focus_scope", "Pane", show=True),
        Binding("left", "focus_scope", "Pane", show=False),
        Binding("l", "focus_list", "Pane", show=False),
        Binding("right", "focus_list", "Pane", show=False),
        Binding("e", "edit", "Edit", show=True),
        Binding("b", "toggle_preview_links", "Backlinks", show=True),
        Binding("space", "toggle_task", "Toggle", show=True),
        Binding("ctrl+d", "delete", "Delete", show=True),
        Binding("/", "open_command_bar", "Filter/command", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._pending_select_id: str | None = None
        self._preview_links_expanded = False
        self._pending_error: str | None = None
        #: The inline editor, while one is open (research R1, data-model
        #: "New state"). `None` is the whole of "not editing" -- every guard
        #: in this screen tests this one field.
        self._editor_pane: EditorPane | None = None
        #: The warning count from `refresh_rows`'s own read, kept as render
        #: output so `_render_status` -- called on every command-bar keystroke
        #: via `ModeChanged` -- never triggers a scan of its own (research R3).
        self._warning_count = 0
        #: The change-detection key from the last render (research R4), so the
        #: periodic refresh tick can tell "nothing changed" without rebuilding.
        self._last_render_key: tuple[tuple[object, ...], ...] = ()
        #: Registered in `on_mount`; paused while a preview, editor, help
        #: screen, or dialog is on top (research R5) so no tick fires while
        #: this screen is not what the user is looking at.
        self._refresh_timer: Timer | None = None
        #: The command-bar session's filter hydration (US3, research R6):
        #: started in `action_open_command_bar`, awaited by `_on_filter_changed`
        #: before the first match, dropped in `_on_command_bar_closed`. Its
        #: lifetime is exactly one bar session (contract C5, plan Complexity
        #: Tracking) -- never consulted once the bar is closed.
        self._filter_hydration: Worker[tuple[list[Document], list[ScanWarning]]] | None = None

    def compose(self) -> ComposeResult:
        yield CollectionBar(
            self.app.active,  # type: ignore[attr-defined]
            str(self.app.workspace.root),  # type: ignore[attr-defined]
            id="collection-bar",
        )
        with Horizontal(id="body"):
            yield ScopePane(id="scope-pane")
            with Vertical(id="list-pane"):
                yield Static(id="list-header")
                yield ListView(id="meeting-list")
            with Vertical(id="preview-pane"):
                yield Markdown(id="preview", open_links=False)
                with Vertical(id="preview-links-section"):
                    yield ListView(id="preview-links-list")
        with Vertical(id="bottom-bar"):
            yield CommandBar(id="command-bar")
            yield StatusBar(LIST_HELP, id="status-bar")

    async def on_mount(self) -> None:
        self.query_one("#preview-links-section").display = False
        await self._refresh_scope_pane()
        self.query_one("#meeting-list", ListView).focus()
        await self.refresh_rows()
        self._refresh_timer = self.set_interval(REFRESH_SECONDS, self._refresh_tick)

    def on_screen_suspend(self) -> None:
        # A preview, editor, help screen, or dialog is now on top -- no tick
        # should fire while this screen is not what is displayed (FR-012).
        if self._refresh_timer is not None:
            self._refresh_timer.pause()

    # --- inline editor (research R1, contract C1/C2) ---------------------------

    def open_inline_editor(self, target: EditTarget) -> None:
        """Mount an `EditorPane` in `#preview-pane` in place of the rendered
        preview (FR-001, FR-003): the collection bar, scope pane, and list
        stay exactly as they are -- only the preview swaps for an editor.
        Freezes the periodic refresh for the duration (research R6) and swaps
        the footer to `EDIT_HELP` (FR-009)."""
        self.query_one("#preview").display = False
        self.query_one("#preview-links-section").display = False
        if self._refresh_timer is not None:
            self._refresh_timer.pause()
        self._editor_pane = EditorPane(target)
        self.query_one("#preview-pane").mount(self._editor_pane)
        self.query_one(StatusBar).update(EDIT_HELP)

    @on(EditorPane.Closed)
    async def _on_editor_pane_closed(self, message: EditorPane.Closed) -> None:
        """The inline editor is done -- unmount it, bring the preview back,
        run the one refresh that a full-screen edit's `on_screen_resume` would
        have run, and land focus back on the list (FR-011, FR-013, contract
        C5). `_pending_select_id` is set by every opener (`action_edit`,
        create, daily-note) the same way it is for the full-screen path."""
        pane = self._editor_pane
        if pane is None:
            return
        self._editor_pane = None
        await pane.remove()
        self.query_one("#preview").display = True
        if self._preview_links_expanded:
            self.query_one("#preview-links-section").display = True
        if self._refresh_timer is not None:
            self._refresh_timer.resume()
        self.query_one(CollectionBar).set_active(self.app.active)  # type: ignore[attr-defined]
        await self._refresh_scope_pane()
        await self.refresh_rows(select_id=self._pending_select_id)
        self._pending_select_id = None
        self.query_one("#meeting-list", ListView).focus()

    def on_resize(self, event: events.Resize) -> None:
        # Column widths are a pure function of the pane's width (research
        # R8) -- re-render the header and every already-rendered row's text
        # in place, with no disk read, rather than re-running the whole
        # refresh (US5).
        self._rerender_columns()

    def _column_layout(self) -> ColumnLayout:
        # Tasks reserve room ahead of the first column for the done marker, which
        # sits outside the four columns (spec Assumptions). Without the lead the
        # header would sit `TASK_LEAD` characters left of the cells it names, and
        # a task row would render `TASK_LEAD` characters wider than the pane.
        lead = TASK_LEAD if self.app.active == "tasks" else 0  # type: ignore[attr-defined]
        return column_widths(self.query_one("#meeting-list", ListView).size.width, lead=lead)

    def _rerender_columns(self) -> None:
        layout = self._column_layout()
        try:
            self.query_one("#list-header", Static).update(render_header(layout))
        except NoMatches:
            return  # not yet mounted
        for row in self.query_one("#meeting-list", ListView).children:
            if isinstance(row, DocumentRow | TaskRow):
                try:
                    row.update_layout(layout)
                except NoMatches:
                    continue  # this row's Label has not finished mounting yet

    def set_pending_status(self, message: str | None) -> None:
        """Receive the outcome of the launch offer raised by `ChoomApp.on_mount`
        (013-assistant-discovery-file, US2, research R6). Stored rather than rendered
        immediately: popping `ConfirmDialog` always triggers this screen's own
        `on_screen_resume` refresh, and rendering here too would race it -- whichever
        finished last would silently overwrite the other's status text. This mirrors
        `_delete_record`'s use of `_pending_error` for exactly the same reason."""
        self._pending_error = message

    async def on_screen_resume(self) -> None:
        # A ConfirmDialog pushed over an open inline editor (research R5) --
        # e.g. the discard confirmation -- resumes this screen when it pops.
        # Refreshing here would call `_update_preview` and overwrite the pane
        # the editor is sitting in, mid-edit; refocus the editor instead and
        # leave the timer paused, exactly as R6 requires while it is mounted.
        if self._editor_pane is not None:
            self._editor_pane.query_one("#editor").focus()
            return
        # Coming back from PreviewScreen/EditScreen: a document may have been
        # created or edited while we were away, and a create moves the active
        # collection/month too -- rebuild everything rather than assume nothing
        # changed. Also fires once at the initial push, coincident with
        # `on_mount`, before `_refresh_timer` exists yet -- `resume()` on an
        # already-running timer is a harmless no-op either way.
        if self._refresh_timer is not None:
            self._refresh_timer.resume()
        self.query_one(CollectionBar).set_active(self.app.active)  # type: ignore[attr-defined]
        await self._refresh_scope_pane()
        await self.refresh_rows(select_id=self._pending_select_id)
        self._pending_select_id = None
        # A delete's outcome (research above `_delete_record`): rendered here,
        # after this resume's own refresh, so it is not the thing that gets
        # overwritten by it.
        if self._pending_error is not None:
            self._render_status(error=self._pending_error)
            self._pending_error = None

    async def _refresh_scope_pane(self) -> None:
        scope_pane = self.query_one(ScopePane)
        app = self.app
        if app.active == "tasks":  # type: ignore[attr-defined]
            await scope_pane.show_categories(highlight=app.task_category)  # type: ignore[attr-defined]
        elif app.filter_query:  # type: ignore[attr-defined]
            await scope_pane.show_suspended(loading=False)
        else:
            listing = app.list_scope(app.active)  # type: ignore[attr-defined]
            highlight = app.scope_selection.get(app.active, app.month_scope[app.active])  # type: ignore[attr-defined]
            await scope_pane.show_months(
                listing.months, has_unfiled=listing.has_unfiled, highlight=highlight
            )

    async def refresh_rows(
        self, *, select_id: str | None = None, reset_selection: bool = False
    ) -> None:
        app = self.app
        list_view = self.query_one("#meeting-list", ListView)
        is_tasks = app.active == "tasks"  # type: ignore[attr-defined]

        if select_id is None and not reset_selection:
            highlighted = list_view.highlighted_child
            if isinstance(highlighted, DocumentRow):
                select_id = highlighted.document.id
            elif isinstance(highlighted, TaskRow):
                select_id = highlighted.record.id

        layout = self._column_layout()
        self.query_one("#list-header", Static).update(render_header(layout))

        await list_view.clear()
        hydrated = self._hydrated_pool()
        if hydrated is not None:
            # A command-bar session's already-hydrated read (US3, research
            # R6): match+sort it directly rather than scanning the collection
            # again for every keystroke after the first (contract C5).
            documents, warnings = hydrated
            items = cast("list[Document | Task]", app.match_documents(documents))  # type: ignore[attr-defined]
            self._warning_count = len(warnings)
        else:
            items = cast(
                "list[Document | Task]",
                app.visible_tasks() if is_tasks else app.visible_documents(),  # type: ignore[attr-defined]
            )
            self._warning_count = len(app.visible_warnings())  # type: ignore[attr-defined]
        self._last_render_key = (
            _task_key(cast("list[Task]", items))
            if is_tasks
            else _document_key(cast("list[Document]", items))
        )
        if not items:
            await list_view.append(ListItem(Label(_empty_state_message(app))))
            list_view.index = 0
        else:
            rows = [
                TaskRow(item, layout) if is_tasks else DocumentRow(item, layout)  # type: ignore[arg-type]
                for item in items
            ]
            await list_view.extend(rows)
            index = 0
            if select_id is not None:
                for i, item in enumerate(items):
                    if item.id == select_id:
                        index = i
                        break
            list_view.index = index
        self._update_preview()
        self._render_status()

    def _hydrated_pool(self) -> tuple[list[Document], list[ScanWarning]] | None:
        """The active command-bar session's hydrated read, if a filter is set
        and the worker has finished (US3, research R6) -- `None` otherwise,
        meaning the caller should read fresh through `app.visible_documents()`.
        Never consulted once the bar has closed (contract C5); the caller
        drops the worker handle in `_on_command_bar_closed`."""
        hydration = self._filter_hydration
        if not self.app.filter_query or hydration is None:  # type: ignore[attr-defined]
            return None
        if not hydration.is_finished or hydration.result is None:
            return None
        return hydration.result

    def _update_preview(self) -> None:
        if self._editor_pane is not None:
            # research R6: a render reached here (e.g. via `refresh_rows` from
            # a filter keystroke) while the inline editor covers `#preview` --
            # writing to it now would be invisible today and stale the moment
            # the editor closes, so skip it rather than waste the render.
            return
        list_view = self.query_one("#meeting-list", ListView)
        preview = self.query_one("#preview", Markdown)
        highlighted = list_view.highlighted_child
        if isinstance(highlighted, DocumentRow):
            preview.update(render_preview_markdown(highlighted.document.path, highlighted.document))
        elif isinstance(highlighted, TaskRow):
            preview.update(render_task_markdown(highlighted.record))
        else:
            preview.update("")

    def _render_status(
        self,
        mode: str | None = None,
        verb: str = "",
        bar_open: bool = False,
        error: str | None = None,
    ) -> None:
        status = self.query_one(StatusBar)
        if error:
            status.update(f"⚠ {error}")
            return
        if bar_open and mode:
            label = f"[command: {verb}]" if mode == "command" else "[filter]"
            status.update(f"{label}   enter run   esc cancel")
            return
        active = self.app.active  # type: ignore[attr-defined]
        help_text = TASK_LIST_HELP if active == "tasks" else LIST_HELP
        text = f"{collection_indicator(active)}   {help_text}"
        warnings = self._warning_count
        if warnings:
            text += f"   {warnings} warning{'s' if warnings != 1 else ''}"
        status.update(text)

    # --- periodic refresh (US2) --------------------------------------------------

    def _refresh_tick_read(
        self,
    ) -> tuple[list[Document | Task], bool, tuple[tuple[object, ...], ...]]:
        """The read step (research R5): identical scope to `refresh_rows`'s own
        read. Touches no widget -- returns the rows, whether they are tasks,
        and the comparison key built from them, which is what a worker thread
        would eventually hand back via `call_from_thread` instead of this
        being called directly on the main thread."""
        app = self.app
        is_tasks = app.active == "tasks"  # type: ignore[attr-defined]
        items = cast(
            "list[Document | Task]",
            app.visible_tasks() if is_tasks else app.visible_documents(),  # type: ignore[attr-defined]
        )
        key = (
            _task_key(cast("list[Task]", items))
            if is_tasks
            else _document_key(cast("list[Document]", items))
        )
        return items, is_tasks, key

    async def _refresh_tick_apply(self, key: tuple[tuple[object, ...], ...]) -> None:
        """The apply step: re-renders via `refresh_rows` -- the same path
        every other caller uses -- only when `key` differs from the last
        render's (FR-010, contract C4). Selection is read fresh right before
        the render it belongs to and passed through by record id, so a
        record that moves position stays selected (FR-011)."""
        if key == self._last_render_key:
            return
        list_view = self.query_one("#meeting-list", ListView)
        highlighted = list_view.highlighted_child
        select_id: str | None = None
        if isinstance(highlighted, DocumentRow):
            select_id = highlighted.document.id
        elif isinstance(highlighted, TaskRow):
            select_id = highlighted.record.id
        await self.refresh_rows(select_id=select_id)

    async def _refresh_tick(self) -> None:
        """Runs every `REFRESH_SECONDS` while this screen is displayed and
        unobstructed (the timer itself is paused otherwise, `on_screen_suspend`/
        `on_screen_resume`). Does nothing while the command bar is open
        (FR-013) or a filter is active (FR-012) -- both are point-in-time
        views that reconcile on their own terms, not the timer's (research R5).
        Also does nothing while the inline editor is open (FR-021, research
        R6) -- the timer is paused on open too; this is the belt to that
        braces, in case a tick was already queued the instant it opened."""
        if self._editor_pane is not None:
            return
        if self.query_one(CommandBar).display or self.app.filter_query:  # type: ignore[attr-defined]
            return
        _items, _is_tasks, key = self._refresh_tick_read()
        await self._refresh_tick_apply(key)

    # --- collection switching (Tab / shift+Tab) --------------------------------

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self._editor_pane is not None:
            # research R2 "belt and braces": no list action runs while the
            # inline editor is open, whether or not the key that triggers it
            # is one `TextArea` would otherwise have absorbed.
            return False
        if action in ("next_collection", "previous_collection", "delete"):
            return not self.query_one(CommandBar).display
        return True

    async def action_next_collection(self) -> None:
        await self._switch_collection_by_offset(1)

    async def action_previous_collection(self) -> None:
        await self._switch_collection_by_offset(-1)

    async def _switch_collection_by_offset(self, offset: int) -> None:
        current = COLLECTIONS.index(self.app.active)  # type: ignore[attr-defined]
        name = COLLECTIONS[(current + offset) % len(COLLECTIONS)]
        await self._activate_collection(name)

    async def _activate_collection(self, name: str) -> None:
        self.app.switch_collection(name)  # type: ignore[attr-defined]
        self.query_one(CollectionBar).set_active(name)
        self._pending_error = None
        await self._refresh_scope_pane()
        await self.refresh_rows(reset_selection=True)
        self.query_one("#meeting-list", ListView).focus()

    # --- pane focus / movement --------------------------------------------------

    def _focused_list(self) -> ListView:
        focused = self.focused
        if isinstance(focused, ListView) and focused.id == "scope-list":
            return focused
        return self.query_one("#meeting-list", ListView)

    def action_cursor_down(self) -> None:
        self._focused_list().action_cursor_down()

    def action_cursor_up(self) -> None:
        self._focused_list().action_cursor_up()

    def action_focus_scope(self) -> None:
        self.query_one("#scope-list", ListView).focus()

    def action_focus_list(self) -> None:
        self.query_one("#meeting-list", ListView).focus()

    def action_open_command_bar(self) -> None:
        if self._editor_pane is not None:
            return  # FR-008: the command bar cannot open while the pane is mounted
        self.query_one(CommandBar).open()
        # Started here, not from `CommandBar.ModeChanged` -- that message is
        # posted on every keystroke, so starting the hydration there would
        # restart the scan per character (research R6). Tasks needs no
        # hydration: filtering it re-reads one file, not every month.
        active = self.app.active  # type: ignore[attr-defined]
        self._filter_hydration = None if active == "tasks" else self._hydrate_filter_pool(active)

    @work(thread=True, exclusive=True, group="filter-hydrate")
    def _hydrate_filter_pool(self, collection: str) -> tuple[list[Document], list[ScanWarning]]:
        """Read the whole of `collection` on a worker thread (US3, research
        R6), so the `/` keypress that opens the command bar never stalls
        (FR-016). Filesystem work does not belong on the event loop -- the
        existing worker precedent is `edit_screen.py`'s AI-request thread.
        `exclusive=True` means a second `/` while one is in flight supersedes
        it rather than racing it.

        `scan_documents` is one walk of the collection's scan dirs, and is what
        the CLI already calls to answer this same question (`scan_meetings`,
        `scan_notes`). The earlier form of this method assembled the same set
        from `scan_month` per month plus `scan_unfiled`, which re-implemented a
        core function in the adapter (Principle I) and walked the tree N+2
        times to core's one -- measurably slower the more months a workspace
        holds: 1.27x at 1,000 documents over 36 months."""
        app = self.app
        descriptor = app.collection_descriptor(collection)  # type: ignore[attr-defined]
        return scan_documents(app.workspace, descriptor)  # type: ignore[attr-defined]

    def action_edit(self) -> None:
        list_view = self.query_one("#meeting-list", ListView)
        highlighted = list_view.highlighted_child

        if self.app.active == "tasks":  # type: ignore[attr-defined]
            if not isinstance(highlighted, TaskRow) or highlighted.record.id is None:
                return
            from choom.tui.edit_screen import open_task_editor

            task = highlighted.record
            self._pending_select_id = task.id
            open_task_editor(self.app, task)
            return

        if not isinstance(highlighted, DocumentRow):
            return
        from choom.tui.edit_screen import open_editor

        document = highlighted.document
        self._pending_select_id = document.id
        open_editor(self.app, document.path)

    async def action_toggle_task(self) -> None:
        if self.app.active != "tasks":  # type: ignore[attr-defined]
            return
        list_view = self.query_one("#meeting-list", ListView)
        highlighted = list_view.highlighted_child
        if not isinstance(highlighted, TaskRow) or highlighted.record.id is None:
            return
        task_id = highlighted.record.id
        self.app.toggle_task_and_track(task_id)  # type: ignore[attr-defined]
        error = self.app.last_task_error  # type: ignore[attr-defined]
        await self.refresh_rows(select_id=task_id)
        if error:
            self._render_status(error=error)

    # --- delete (ctrl+d, US2) ----------------------------------------------------

    async def action_delete(self) -> None:
        list_view = self.query_one("#meeting-list", ListView)
        highlighted = list_view.highlighted_child

        record_id: str | None
        title: str
        if isinstance(highlighted, DocumentRow):
            record_id = highlighted.document.id
            title = highlighted.document.title
        elif isinstance(highlighted, TaskRow):
            record_id = highlighted.record.id
            title = highlighted.record.text
        else:
            return  # no record highlighted -- the empty-state row, or nothing (FR-014)
        if record_id is None:
            return

        # Captured now, acted on when the dialog returns (FR-010, research
        # R11) -- a background re-read cannot redirect the delete onto a
        # different record, whether or not it can even run while the dialog
        # (a ModalScreen) suspends this one.
        captured_id = record_id
        dialog = ConfirmDialog(
            f'Delete "{title}"? This cannot be undone.',
            cancel_label="Keep It",
            confirm_label="Delete",
        )

        async def _handle_dismiss(confirmed: bool | None) -> None:
            if confirmed:
                await self._delete_record(captured_id)

        self.app.push_screen(dialog, _handle_dismiss)

    async def _delete_record(self, record_id: str) -> None:
        """Delete `record_id` and arrange for the next `on_screen_resume` --
        which fires as soon as `ConfirmDialog` finishes popping itself off the
        screen stack -- to render the outcome.

        Deliberately does *not* call `refresh_rows`/`_render_status` directly:
        popping the dialog always triggers `on_screen_resume`'s own refresh on
        this screen, and a second, independent refresh from here would race
        it -- whichever finished last would silently overwrite the other's
        status text. Setting `_pending_select_id`/`_pending_error` here and
        letting `on_screen_resume` be the one place that renders keeps there
        being exactly one refresh for this whole gesture.
        """
        workspace: Workspace = self.app.workspace  # type: ignore[attr-defined]
        list_view = self.query_one("#meeting-list", ListView)
        ids_in_order = [
            row_id
            for row in list_view.children
            if isinstance(row, DocumentRow | TaskRow)
            and (row_id := (row.document.id if isinstance(row, DocumentRow) else row.record.id))
            is not None
        ]

        try:
            delete_by_id(workspace, record_id)
        except (NotFoundError, UsageError, WorkspaceError) as exc:
            self._pending_error = str(exc)
            return

        self._pending_select_id = self._next_highlight_id(ids_in_order, record_id)

    @staticmethod
    def _next_highlight_id(ids_in_order: list[str], deleted_id: str) -> str | None:
        """Which record should be highlighted once `deleted_id` is gone from a
        list rendered in `ids_in_order`: the next record, or the previous one
        when the deleted record was last, or `None` when it was the only one
        (FR-011, FR-012)."""
        try:
            index = ids_in_order.index(deleted_id)
        except ValueError:
            return None
        remaining = ids_in_order[:index] + ids_in_order[index + 1 :]
        if not remaining:
            return None
        return remaining[index] if index < len(remaining) else remaining[-1]

    # --- scope pane interaction --------------------------------------------------

    @on(ListView.Highlighted, "#scope-list")
    async def _on_scope_highlighted(self, event: ListView.Highlighted) -> None:
        # `ScopePane.show_months`/`show_categories` repopulate via `ListView.extend`,
        # which itself fires a Highlighted message for the row that lands on top --
        # a side effect of *our* refresh, not the user moving the highlight. Skip
        # when the reported selection already matches session state, or every
        # programmatic repopulation would trigger a second, overlapping
        # `refresh_rows` and double the rendered rows.
        item = event.item
        app = self.app
        active = app.active  # type: ignore[attr-defined]
        if isinstance(item, MonthRow):
            if app.scope_selection.get(active) == item.month:  # type: ignore[attr-defined]
                return
            app.select_scope(active, item.month)  # type: ignore[attr-defined]
        elif isinstance(item, UnfiledRow):
            if app.scope_selection.get(active) == "unfiled":  # type: ignore[attr-defined]
                return
            app.select_scope(active, "unfiled")  # type: ignore[attr-defined]
        elif isinstance(item, CategoryRow):
            if app.task_category == item.category:  # type: ignore[attr-defined]
                return
            app.task_category = item.category  # type: ignore[attr-defined]
        else:
            return
        await self.refresh_rows(reset_selection=True)

    # --- list pane interaction --------------------------------------------------

    @on(ListView.Highlighted, "#meeting-list")
    def _on_highlighted(self, event: ListView.Highlighted) -> None:
        self._update_preview()
        if self._preview_links_expanded:
            # The pane describes whatever row is highlighted, so moving the
            # cursor has to re-fetch rather than leave a stale record's links on
            # screen. The inbound scan is the cost of having it open.
            self.call_later(self._populate_preview_links)

    # --- Links pane (b) ---------------------------------------------------------

    async def action_toggle_preview_links(self) -> None:
        section = self.query_one("#preview-links-section")
        if self._preview_links_expanded:
            self._preview_links_expanded = False
            section.display = False
            self.query_one("#meeting-list", ListView).focus()
            return
        self._preview_links_expanded = True
        section.display = True
        await self._populate_preview_links()
        self.query_one("#preview-links-list", ListView).focus()

    async def _populate_preview_links(self) -> None:
        list_view = self.query_one("#preview-links-list", ListView)
        await list_view.clear()

        workspace: Workspace = self.app.workspace  # type: ignore[attr-defined]
        highlighted = self.query_one("#meeting-list", ListView).highlighted_child
        source: Path
        document_id: str | None
        if isinstance(highlighted, DocumentRow):
            source, document_id = highlighted.document.path, highlighted.document.id
        elif isinstance(highlighted, TaskRow):
            source, document_id = workspace.tasks_file, highlighted.record.id
        else:
            return

        inbound = fetch_inbound(workspace, document_id)
        await list_view.extend(build_link_rows(workspace, source, document_id, inbound))

    @on(ListView.Selected, "#preview-links-list")
    def _on_preview_link_selected(self, event: ListView.Selected) -> None:
        row = event.item
        if not isinstance(row, LinkRow):
            return
        if row.target is None:
            unresolved = row.link.target_id or row.link.path or "?"
            self.query_one(StatusBar).update(
                f"⚠ link to {unresolved!r} does not resolve   {LIST_HELP}"
            )
            return
        self._open_link_target(row.target)

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        """Follow a link clicked in the preview pane's rendered body.

        Same rule as the full-screen preview: a link choom owns opens the
        record it names, and anything else goes to the browser, which is what
        `Markdown` would have done with every href had `open_links` been left on.
        """
        workspace: Workspace = self.app.workspace  # type: ignore[attr-defined]
        highlighted = self.query_one("#meeting-list", ListView).highlighted_child
        source = (
            highlighted.document.path
            if isinstance(highlighted, DocumentRow)
            else workspace.tasks_file
        )

        target = resolve_href(workspace, source, event.href)
        if target is None:
            self.app.open_url(event.href)
            return
        self._open_link_target(target)

    def _open_link_target(self, target: LinkTarget) -> None:
        """Open a record named by a link -- from a click in the rendered body or
        from `enter` in the links pane. One path, so the two cannot diverge."""
        if target.kind == "task":
            from choom.tui.edit_screen import open_editor

            open_editor(self.app, target.path)
            return

        from choom.tui.preview_screen import PreviewScreen

        # Deliberately *not* setting `_pending_select_id`. That exists so that
        # opening the row you are on returns you to it. Following a link is the
        # opposite motion -- you went somewhere else -- and `esc` means "back"
        # everywhere in this app, so it must return to the record you left, not
        # strand you on the one you visited. `refresh_rows` keeps the current
        # highlight when no id is pending, which is exactly that behaviour.
        self.app.push_screen(PreviewScreen(target.path, _read_document(target.path)))

    @on(ListView.Selected, "#meeting-list")
    def _on_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, DocumentRow):
            from choom.tui.preview_screen import PreviewScreen

            document = event.item.document
            self._pending_select_id = document.id
            # Read fresh rather than pass the row's `Document` -- matches
            # `action_open_preview`/`_open_link_target`, so every path into the
            # preview shows the file as it is now, not as it was when this row
            # was rendered (010-read-on-load, research R7, FR-003).
            self.app.push_screen(PreviewScreen(document.path, _read_document(document.path)))

    # --- command bar --------------------------------------------------------

    @on(CommandBar.ModeChanged)
    def _on_mode_changed(self, message: CommandBar.ModeChanged) -> None:
        self._render_status(mode=message.mode, verb=message.verb, bar_open=True)

    @on(CommandBar.FilterChanged)
    async def _on_filter_changed(self, message: CommandBar.FilterChanged) -> None:
        self.app.set_filter(message.query)  # type: ignore[attr-defined]
        if self._filter_hydration is not None:
            # Waits for the read started when the bar opened, so the first
            # term matches the whole collection rather than a partial set
            # (FR-017). A failed or superseded hydration falls back to
            # `refresh_rows`'s own scan via `_hydrated_pool` returning None.
            try:
                await self._filter_hydration.wait()
            except (WorkerFailed, WorkerCancelled):
                pass
        await self._refresh_scope_pane()
        await self.refresh_rows(reset_selection=True)

    @on(CommandBar.CreateRequested)
    async def _on_create_requested(self, message: CommandBar.CreateRequested) -> None:
        if message.kind == "task":
            task = self.app.add_task_and_track(  # type: ignore[attr-defined]
                message.description, message.type
            )
            if task is not None:
                self._pending_error = None
                # Only refill the panes when Tasks is the view being shown --
                # from any other collection, the task is added in the
                # background and the current view is left untouched.
                if self.app.active == "tasks":  # type: ignore[attr-defined]
                    await self._refresh_scope_pane()
                    await self.refresh_rows(select_id=task.id)
            else:
                self._pending_error = self.app.last_create_error  # type: ignore[attr-defined]
            return
        if message.kind == "note":
            document = self.app.create_note_and_track(  # type: ignore[attr-defined]
                message.description, message.type
            )
        else:
            document = self.app.create_meeting_and_track(  # type: ignore[attr-defined]
                message.description, message.type
            )
        if document is not None:
            from choom.tui.edit_screen import open_editor

            self._pending_error = None
            self._pending_select_id = document.id
            # Select the new record before opening the editor, not after
            # (research R8, FR-016): inline, the list is in plain view beside
            # the editor for the whole edit, so it must already agree about
            # what is being edited rather than catching up once the pane
            # closes and covers the mismatch.
            self.query_one(CollectionBar).set_active(self.app.active)  # type: ignore[attr-defined]
            await self._refresh_scope_pane()
            await self.refresh_rows(select_id=document.id)
            open_editor(self.app, document.path)
        else:
            self._pending_error = self.app.last_create_error  # type: ignore[attr-defined]

    @on(CommandBar.DailyRequested)
    async def _on_daily_requested(self, message: CommandBar.DailyRequested) -> None:
        daily = self.app.open_daily_note_and_track()  # type: ignore[attr-defined]
        from choom.tui.edit_screen import open_editor

        self._pending_error = None
        select_id = daily.document.id if daily.document is not None else None
        self._pending_select_id = select_id
        # Same ordering as _on_create_requested (research R8): select first.
        self.query_one(CollectionBar).set_active(self.app.active)  # type: ignore[attr-defined]
        await self._refresh_scope_pane()
        await self.refresh_rows(select_id=select_id)
        # The editor reads raw text regardless of whether frontmatter parses, so an
        # existing-but-malformed daily note is still editable, not blocked (FR-022).
        open_editor(self.app, daily.path)

    @on(CommandBar.CollectionRequested)
    async def _on_collection_requested(self, message: CommandBar.CollectionRequested) -> None:
        await self._activate_collection(message.name)

    @on(CommandBar.ConfigRequested)
    def _on_config_requested(self, message: CommandBar.ConfigRequested) -> None:
        self._pending_error = self.app.handle_config_command(message.argument)  # type: ignore[attr-defined]

    @on(CommandBar.HelpRequested)
    def _on_help_requested(self, message: CommandBar.HelpRequested) -> None:
        self.app.push_screen(HelpScreen())

    @on(CommandBar.BarError)
    def _on_bar_error(self, message: CommandBar.BarError) -> None:
        self._pending_error = message.message

    @on(CommandBar.Closed)
    def _on_command_bar_closed(self, message: CommandBar.Closed) -> None:
        # The snapshot's lifetime is exactly one bar session (FR-019, contract
        # C5) -- a filter left showing after the bar closes is a point-in-time
        # answer that reconciles when cleared, not on the next keystroke.
        self._filter_hydration = None
        self._render_status(error=self._pending_error)
        self._pending_error = None
        self.query_one("#meeting-list", ListView).focus()
