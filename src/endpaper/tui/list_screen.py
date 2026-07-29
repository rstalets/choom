from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Markdown

from endpaper.core.models import Meeting
from endpaper.tui.command_bar import CommandBar
from endpaper.tui.rendering import render_preview_markdown
from endpaper.tui.status_bar import LIST_HELP, StatusBar

EMPTY_STATE_MESSAGE = "No meetings yet. Press / then 'meeting <description>' to create one."


class MeetingRow(ListItem):
    def __init__(self, meeting: Meeting) -> None:
        super().__init__(Label(self._row_text(meeting)))
        self.meeting = meeting

    @staticmethod
    def _row_text(meeting: Meeting) -> str:
        parts = [meeting.created[:10]]
        if meeting.type:
            parts.append(meeting.type)
        parts.append(meeting.title)
        if meeting.tags:
            parts.append(",".join(meeting.tags))
        return "  ".join(parts)


class ListScreen(Screen[None]):
    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("/", "open_command_bar", "Filter/command"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._last_previewed_id: str | None = None
        self._pending_error: str | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="body"):
            with Vertical(id="list-pane"):
                yield ListView(id="meeting-list")
            with Vertical(id="preview-pane"):
                yield Markdown(id="preview")
        with Vertical(id="bottom-bar"):
            yield CommandBar(id="command-bar")
            yield StatusBar(LIST_HELP, id="status-bar")

    def on_mount(self) -> None:
        self.query_one("#meeting-list", ListView).focus()
        self.refresh_rows()

    def on_screen_resume(self) -> None:
        # Coming back from PreviewScreen: a meeting may have been created while we
        # were away (command bar create lands straight in preview, without ever
        # selecting a row), so the rows built at initial mount are potentially
        # stale. Rebuild, preferring the meeting that was actually being previewed
        # over whatever the list happened to have highlighted before it was opened.
        self.refresh_rows(select_id=self._last_previewed_id)

    def refresh_rows(self, *, select_id: str | None = None) -> None:
        app = self.app
        list_view = self.query_one("#meeting-list", ListView)

        if select_id is None:
            highlighted = list_view.highlighted_child
            if isinstance(highlighted, MeetingRow):
                select_id = highlighted.meeting.id

        list_view.clear()
        meetings = app.visible_meetings  # type: ignore[attr-defined]
        if not meetings:
            list_view.append(ListItem(Label(EMPTY_STATE_MESSAGE)))
        else:
            for meeting in meetings:
                list_view.append(MeetingRow(meeting))
            index = 0
            if select_id is not None:
                for i, meeting in enumerate(meetings):
                    if meeting.id == select_id:
                        index = i
                        break
            list_view.index = index
        self._update_preview()
        self._render_status()

    def _update_preview(self) -> None:
        list_view = self.query_one("#meeting-list", ListView)
        preview = self.query_one("#preview", Markdown)
        highlighted = list_view.highlighted_child
        if isinstance(highlighted, MeetingRow):
            preview.update(render_preview_markdown(highlighted.meeting))
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
        text = LIST_HELP
        warnings = len(self.app.warnings)  # type: ignore[attr-defined]
        if warnings:
            text += f"   {warnings} warning{'s' if warnings != 1 else ''}"
        status.update(text)

    @on(ListView.Highlighted, "#meeting-list")
    def _on_highlighted(self, event: ListView.Highlighted) -> None:
        self._update_preview()

    @on(ListView.Selected, "#meeting-list")
    def _on_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, MeetingRow):
            from endpaper.tui.preview_screen import PreviewScreen

            self._last_previewed_id = event.item.meeting.id
            self.app.push_screen(PreviewScreen(event.item.meeting))

    def action_cursor_down(self) -> None:
        self.query_one("#meeting-list", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#meeting-list", ListView).action_cursor_up()

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
        meeting = self.app.create_meeting_and_track(  # type: ignore[attr-defined]
            message.description, message.type
        )
        if meeting is not None:
            from endpaper.tui.preview_screen import PreviewScreen

            self._last_previewed_id = meeting.id
            self._pending_error = None
            self.app.push_screen(PreviewScreen(meeting))
        else:
            self._pending_error = self.app.last_create_error  # type: ignore[attr-defined]

    @on(CommandBar.Closed)
    def _on_command_bar_closed(self, message: CommandBar.Closed) -> None:
        self._render_status(error=self._pending_error)
        self._pending_error = None
        self.query_one("#meeting-list", ListView).focus()
