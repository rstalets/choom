from __future__ import annotations

from dataclasses import replace

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import TextArea

from endpaper.core.editing import save_buffer
from endpaper.core.models import EditableFile
from endpaper.tui.discard_dialog import DiscardDialog
from endpaper.tui.status_bar import EDIT_HELP, StatusBar


class EditScreen(Screen[None]):
    # TextArea itself binds ctrl+o is unbound but ctrl+s/ctrl+x are (cut); `priority=True`
    # means these are checked app-down-to-focused-widget, before TextArea's own
    # bindings, so they aren't shadowed by the focused editor (e.g. TextArea's
    # built-in ctrl+x -> cut).
    BINDINGS = [
        Binding("ctrl+o", "save", "Save", show=True, priority=True),
        Binding("ctrl+s", "save", "Save", show=False, priority=True),
        Binding("ctrl+x", "save_and_close", "Save & close", show=True, priority=True),
        Binding("escape", "close", "Discard", show=True),
    ]

    def __init__(self, file: EditableFile) -> None:
        super().__init__()
        self.file = file
        self.original_text = file.text

    @property
    def is_dirty(self) -> bool:
        return self.query_one("#editor", TextArea).text != self.original_text

    def compose(self) -> ComposeResult:
        yield TextArea(self.file.text, show_line_numbers=True, id="editor")
        with Vertical(id="bottom-bar"):
            yield StatusBar(EDIT_HELP, id="status-bar")

    def on_mount(self) -> None:
        self.query_one("#editor", TextArea).focus()

    def _render_status(self, note: str | None = None) -> None:
        status = self.query_one(StatusBar)
        status.update(f"⚠ {note}   {EDIT_HELP}" if note else EDIT_HELP)

    def _save(self) -> bool:
        editor = self.query_one("#editor", TextArea)
        result = save_buffer(self.file.path, editor.text, self.file)
        if not result.ok:
            self._render_status(result.message)
            return False

        if result.saved_text != editor.text:
            # The stamp changed the `updated:` line -- sync the buffer to match
            # what actually landed on disk, or the widget would read as dirty
            # the instant it saved (whenever the new timestamp differs from
            # what's still displayed). `load_text` resets cursor/selection, so
            # capture and restore it around the reload (FR-014).
            cursor = editor.cursor_location
            editor.text = result.saved_text
            editor.cursor_location = cursor

        self.original_text = result.saved_text
        self.file = replace(self.file, text=result.saved_text)
        self.app.refresh_document(self.file.path)  # type: ignore[attr-defined]
        if not result.stamped:
            self._render_status("frontmatter's updated: field could not be found; saved as typed")
        else:
            self._render_status(None)
        return True

    def action_save(self) -> None:
        self._save()

    def action_save_and_close(self) -> None:
        if self._save():
            self.app.pop_screen()

    def action_close(self) -> None:
        if not self.is_dirty:
            self.app.pop_screen()
            return

        def _handle_dismiss(discard: bool | None) -> None:
            if discard:
                self.app.pop_screen()
            else:
                self.query_one("#editor", TextArea).focus()

        self.app.push_screen(DiscardDialog(), _handle_dismiss)
