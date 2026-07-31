from __future__ import annotations

from typing import cast

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Markdown

from endpaper.core.models import Document, Task, YearMonth
from endpaper.tui.collection_bar import COLLECTIONS, CollectionBar
from endpaper.tui.command_bar import CommandBar
from endpaper.tui.help_screen import HelpScreen
from endpaper.tui.rendering import render_preview_markdown
from endpaper.tui.scope_pane import CategoryRow, MonthRow, ScopePane, UnfiledRow
from endpaper.tui.status_bar import LIST_HELP, TASK_LIST_HELP, StatusBar, collection_indicator

_EMPTY_STATE = {
    "meetings": "No meetings yet. Press / then 'meeting <description>' to create one.",
    "notes": "No notes yet. Press / then 'note' for today's note, or 'note <description>'.",
    "tasks": "No tasks yet. Press / then 'task <description>' to create one.",
}
_CREATE_VERB = {"meetings": "meeting", "notes": "note"}


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
    def __init__(self, document: Document) -> None:
        super().__init__(Label(self._row_text(document)))
        self.document = document

    @property
    def meeting(self) -> Document:
        """Feature 001 compatibility alias for `document`."""
        return self.document

    @staticmethod
    def _row_text(document: Document) -> str:
        parts = [document.created[:10]]
        if document.type:
            parts.append(document.type)
        parts.append(document.title)
        if document.tags:
            parts.append(",".join(document.tags))
        return "  ".join(parts)


MeetingRow = DocumentRow  # alias, feature 001 compatibility


class TaskRow(ListItem):
    def __init__(self, task: Task) -> None:
        text = self._row_text(task)
        if task.done:
            text = f"[strike]{text}[/strike]"
        super().__init__(Label(text))
        self.record = task

    @staticmethod
    def _row_text(task: Task) -> str:
        parts = ["[x]" if task.done else "[ ]"]
        if task.created:
            parts.append(task.created.isoformat())
        if task.type:
            parts.append(task.type)
        parts.append(task.text)
        if task.tags:
            parts.append(",".join(task.tags))
        return "  ".join(parts)


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
        Binding("space", "toggle_task", "Toggle", show=True),
        Binding("/", "open_command_bar", "Filter/command", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._pending_select_id: str | None = None
        self._pending_error: str | None = None

    def compose(self) -> ComposeResult:
        yield CollectionBar(self.app.active, id="collection-bar")  # type: ignore[attr-defined]
        with Horizontal(id="body"):
            yield ScopePane(id="scope-pane")
            with Vertical(id="list-pane"):
                yield ListView(id="meeting-list")
            with Vertical(id="preview-pane"):
                yield Markdown(id="preview")
        with Vertical(id="bottom-bar"):
            yield CommandBar(id="command-bar")
            yield StatusBar(LIST_HELP, id="status-bar")

    async def on_mount(self) -> None:
        await self._refresh_scope_pane()
        self.query_one("#meeting-list", ListView).focus()
        await self.refresh_rows()

    async def on_screen_resume(self) -> None:
        # Coming back from PreviewScreen/EditScreen: a document may have been
        # created or edited while we were away, and a create moves the active
        # collection/month too -- rebuild everything rather than assume nothing
        # changed.
        self.query_one(CollectionBar).set_active(self.app.active)  # type: ignore[attr-defined]
        await self._refresh_scope_pane()
        await self.refresh_rows(select_id=self._pending_select_id)
        self._pending_select_id = None

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

        await list_view.clear()
        items = cast(
            "list[Document | Task]",
            app.visible_tasks() if is_tasks else app.visible_documents(),  # type: ignore[attr-defined]
        )
        if not items:
            await list_view.append(ListItem(Label(_empty_state_message(app))))
            list_view.index = 0
        else:
            rows = [TaskRow(item) if is_tasks else DocumentRow(item) for item in items]  # type: ignore[arg-type]
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

    def _update_preview(self) -> None:
        list_view = self.query_one("#meeting-list", ListView)
        preview = self.query_one("#preview", Markdown)
        highlighted = list_view.highlighted_child
        if isinstance(highlighted, DocumentRow):
            preview.update(render_preview_markdown(highlighted.document.path, highlighted.document))
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
        warnings = len(self.app.visible_warnings())  # type: ignore[attr-defined]
        if warnings:
            text += f"   {warnings} warning{'s' if warnings != 1 else ''}"
        status.update(text)

    # --- collection switching (Tab / shift+Tab) --------------------------------

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in ("next_collection", "previous_collection"):
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
        self.query_one(CommandBar).open()

    def action_edit(self) -> None:
        if self.app.active == "tasks":  # type: ignore[attr-defined]
            return
        list_view = self.query_one("#meeting-list", ListView)
        highlighted = list_view.highlighted_child
        if not isinstance(highlighted, DocumentRow):
            return
        from endpaper.tui.edit_screen import open_editor

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

    @on(ListView.Selected, "#meeting-list")
    def _on_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, DocumentRow):
            from endpaper.tui.preview_screen import PreviewScreen

            document = event.item.document
            self._pending_select_id = document.id
            self.app.push_screen(PreviewScreen(document.path, document))

    # --- command bar --------------------------------------------------------

    @on(CommandBar.ModeChanged)
    def _on_mode_changed(self, message: CommandBar.ModeChanged) -> None:
        self._render_status(mode=message.mode, verb=message.verb, bar_open=True)

    @on(CommandBar.FilterChanged)
    async def _on_filter_changed(self, message: CommandBar.FilterChanged) -> None:
        self.app.set_filter(message.query)  # type: ignore[attr-defined]
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
            from endpaper.tui.edit_screen import open_editor

            self._pending_select_id = document.id
            self._pending_error = None
            open_editor(self.app, document.path)
        else:
            self._pending_error = self.app.last_create_error  # type: ignore[attr-defined]

    @on(CommandBar.DailyRequested)
    def _on_daily_requested(self, message: CommandBar.DailyRequested) -> None:
        daily = self.app.open_daily_note_and_track()  # type: ignore[attr-defined]
        from endpaper.tui.edit_screen import open_editor

        self._pending_error = None
        self._pending_select_id = daily.document.id if daily.document is not None else None
        # The editor reads raw text regardless of whether frontmatter parses, so an
        # existing-but-malformed daily note is still editable, not blocked (FR-022).
        open_editor(self.app, daily.path)

    @on(CommandBar.CollectionRequested)
    async def _on_collection_requested(self, message: CommandBar.CollectionRequested) -> None:
        await self._activate_collection(message.name)

    @on(CommandBar.HelpRequested)
    def _on_help_requested(self, message: CommandBar.HelpRequested) -> None:
        self.app.push_screen(HelpScreen())

    @on(CommandBar.BarError)
    def _on_bar_error(self, message: CommandBar.BarError) -> None:
        self._pending_error = message.message

    @on(CommandBar.Closed)
    def _on_command_bar_closed(self, message: CommandBar.Closed) -> None:
        self._render_status(error=self._pending_error)
        self._pending_error = None
        self.query_one("#meeting-list", ListView).focus()
