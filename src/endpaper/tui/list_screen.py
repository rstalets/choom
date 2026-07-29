from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Markdown

from endpaper.core.models import Document
from endpaper.tui.command_bar import CommandBar
from endpaper.tui.rendering import render_preview_markdown
from endpaper.tui.status_bar import LIST_HELP, StatusBar, collection_indicator

EMPTY_STATE_MESSAGE = "No meetings yet. Press / then 'meeting <description>' to create one."
_NOTES_EMPTY_STATE_MESSAGE = (
    "No notes yet. Press / then 'note' for today's note, or 'note <description>'."
)

COLLECTIONS = ("meetings", "notes")
_COLLECTION_LABELS = {"meetings": "Meetings", "notes": "Notes"}


def _empty_state_message(active: str) -> str:
    return _NOTES_EMPTY_STATE_MESSAGE if active == "notes" else EMPTY_STATE_MESSAGE


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


class CollectionRow(ListItem):
    def __init__(self, name: str) -> None:
        super().__init__(Label(_COLLECTION_LABELS[name]))
        self.collection_name = name


class ListScreen(Screen[None]):
    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("h", "focus_menu", "Menu"),
        ("left", "focus_menu", "Menu"),
        ("l", "focus_list", "List"),
        ("right", "focus_list", "List"),
        ("/", "open_command_bar", "Filter/command"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._last_previewed_id: str | None = None
        self._pending_error: str | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="body"):
            with Vertical(id="menu-pane"):
                yield ListView(id="collection-menu")
            with Vertical(id="list-pane"):
                yield ListView(id="meeting-list")
            with Vertical(id="preview-pane"):
                yield Markdown(id="preview")
        with Vertical(id="bottom-bar"):
            yield CommandBar(id="command-bar")
            yield StatusBar(LIST_HELP, id="status-bar")

    def on_mount(self) -> None:
        menu = self.query_one("#collection-menu", ListView)
        for name in COLLECTIONS:
            menu.append(CollectionRow(name))
        self.query_one("#meeting-list", ListView).focus()
        self.refresh_rows()

    def on_screen_resume(self) -> None:
        # Coming back from PreviewScreen: a document may have been created while we
        # were away (command bar create lands straight in preview, without ever
        # selecting a row), so the rows built at initial mount are potentially
        # stale. Rebuild, preferring the document that was actually being previewed
        # over whatever the list happened to have highlighted before it was opened.
        self.refresh_rows(select_id=self._last_previewed_id)

    def _sync_menu_highlight(self) -> None:
        menu = self.query_one("#collection-menu", ListView)
        active = self.app.active  # type: ignore[attr-defined]
        index = COLLECTIONS.index(active)
        if menu.index != index:
            menu.index = index

    def refresh_rows(self, *, select_id: str | None = None, reset_selection: bool = False) -> None:
        app = self.app
        list_view = self.query_one("#meeting-list", ListView)

        if select_id is None and not reset_selection:
            highlighted = list_view.highlighted_child
            if isinstance(highlighted, DocumentRow):
                select_id = highlighted.document.id

        list_view.clear()
        documents = app.visible_documents  # type: ignore[attr-defined]
        if not documents:
            list_view.append(ListItem(Label(_empty_state_message(app.active))))  # type: ignore[attr-defined]
        else:
            for document in documents:
                list_view.append(DocumentRow(document))
            index = 0
            if select_id is not None:
                for i, document in enumerate(documents):
                    if document.id == select_id:
                        index = i
                        break
            list_view.index = index
        self._sync_menu_highlight()
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
        text = f"{collection_indicator(active)}   {LIST_HELP}"
        warnings = len(self.app.warnings[active])  # type: ignore[attr-defined]
        if warnings:
            text += f"   {warnings} warning{'s' if warnings != 1 else ''}"
        status.update(text)

    @on(ListView.Highlighted, "#meeting-list")
    def _on_highlighted(self, event: ListView.Highlighted) -> None:
        self._update_preview()

    @on(ListView.Selected, "#meeting-list")
    def _on_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, DocumentRow):
            from endpaper.tui.preview_screen import PreviewScreen

            document = event.item.document
            self._last_previewed_id = document.id
            self.app.push_screen(PreviewScreen(document.path, document))

    @on(ListView.Highlighted, "#collection-menu")
    def _on_menu_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, CollectionRow) and item.collection_name != self.app.active:  # type: ignore[attr-defined]
            self.app.switch_collection(item.collection_name)  # type: ignore[attr-defined]
            self.refresh_rows(reset_selection=True)

    @on(ListView.Selected, "#collection-menu")
    def _on_menu_selected(self, event: ListView.Selected) -> None:
        self.query_one("#meeting-list", ListView).focus()

    def _focused_list(self) -> ListView:
        focused = self.focused
        if isinstance(focused, ListView) and focused.id == "collection-menu":
            return focused
        return self.query_one("#meeting-list", ListView)

    def action_cursor_down(self) -> None:
        self._focused_list().action_cursor_down()

    def action_cursor_up(self) -> None:
        self._focused_list().action_cursor_up()

    def action_focus_menu(self) -> None:
        self.query_one("#collection-menu", ListView).focus()

    def action_focus_list(self) -> None:
        self.query_one("#meeting-list", ListView).focus()

    def action_open_command_bar(self) -> None:
        self.query_one(CommandBar).open()

    @on(CommandBar.ModeChanged)
    def _on_mode_changed(self, message: CommandBar.ModeChanged) -> None:
        self._render_status(mode=message.mode, verb=message.verb, bar_open=True)

    @on(CommandBar.FilterChanged)
    def _on_filter_changed(self, message: CommandBar.FilterChanged) -> None:
        self.app.apply_filter(message.query)  # type: ignore[attr-defined]
        self.refresh_rows()

    @on(CommandBar.ClearRequested)
    def _on_clear_requested(self, message: CommandBar.ClearRequested) -> None:
        self.app.apply_filter("")  # type: ignore[attr-defined]
        self.refresh_rows()

    @on(CommandBar.CreateRequested)
    def _on_create_requested(self, message: CommandBar.CreateRequested) -> None:
        if message.kind == "note":
            document = self.app.create_note_and_track(  # type: ignore[attr-defined]
                message.description, message.type
            )
        else:
            document = self.app.create_meeting_and_track(  # type: ignore[attr-defined]
                message.description, message.type
            )
        if document is not None:
            from endpaper.tui.preview_screen import PreviewScreen

            self._last_previewed_id = document.id
            self._pending_error = None
            self.app.push_screen(PreviewScreen(document.path, document))
        else:
            self._pending_error = self.app.last_create_error  # type: ignore[attr-defined]

    @on(CommandBar.DailyRequested)
    def _on_daily_requested(self, message: CommandBar.DailyRequested) -> None:
        daily = self.app.open_daily_note_and_track()  # type: ignore[attr-defined]
        from endpaper.tui.preview_screen import PreviewScreen

        if daily.document is not None:
            self._last_previewed_id = daily.document.id
            self._pending_error = None
            self.app.push_screen(PreviewScreen(daily.path, daily.document))
        else:
            self._pending_error = None
            self.app.push_screen(
                PreviewScreen(daily.path, None, note="frontmatter could not be read")
            )

    @on(CommandBar.CollectionRequested)
    def _on_collection_requested(self, message: CommandBar.CollectionRequested) -> None:
        self.app.switch_collection(message.name)  # type: ignore[attr-defined]
        self._pending_error = None
        self.refresh_rows(reset_selection=True)

    @on(CommandBar.BarError)
    def _on_bar_error(self, message: CommandBar.BarError) -> None:
        self._pending_error = message.message

    @on(CommandBar.Closed)
    def _on_command_bar_closed(self, message: CommandBar.Closed) -> None:
        self._render_status(error=self._pending_error)
        self._pending_error = None
        self.query_one("#meeting-list", ListView).focus()
