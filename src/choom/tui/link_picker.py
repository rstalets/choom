"""The link picker: a bounded, wrapping selection list for an ambiguous
`/link` search (research R1-R3, contracts/tui.md). Composed hidden into each
host screen's `#bottom-bar`; `EditorPane` reaches it with
`self.screen.query_one(LinkPicker)`, the same idiom `_render_status` already
uses for `StatusBar`, so one code path serves both hosts (FR-004).

`open()`/`close()`, plus the `Chosen`/`Cancelled` messages it posts, are this
widget's whole outward contract -- it never edits the document itself.
"""

from __future__ import annotations

from textual import events
from textual._loop import loop_from_index
from textual.binding import Binding
from textual.message import Message
from textual.widget import AwaitMount
from textual.widgets import Label, ListItem, ListView

from choom.core.models import LinkCandidate
from choom.tui.rendering import render_candidate_row
from choom.tui.status_bar import link_ambiguous_status


class _CandidateRow(ListItem):
    """One row in the picker, carrying the candidate it represents."""

    def __init__(self, candidate: LinkCandidate, label: str) -> None:
        super().__init__(Label(label))
        self.candidate = candidate


class LinkPicker(ListView):
    """A bounded, wrapping list of `LinkCandidate` rows (contracts/tui.md C1,
    C2). Mounted hidden (`display = False`) for the life of its host screen;
    `open()` shows it with a fresh set of candidates, `close()` hides it and
    drops them -- the resting state.

    `↑`/`↓` wrap at both ends (research R3, FR-006): `ListView`'s own
    `action_cursor_down`/`action_cursor_up` call Textual's `loop_from_index`
    with `wrap=False` (verified against the installed Textual 8.2.8);
    overriding just that argument is the whole change. `enter` stays
    `ListView`'s own binding -- it posts `Selected`, handled below into
    `Chosen`. `escape` cancels.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    class Chosen(Message):
        """Posted when `enter` selects a row. The host resolves and inserts;
        this widget never touches the buffer itself."""

        def __init__(self, candidate: LinkCandidate) -> None:
            self.candidate = candidate
            super().__init__()

    class Cancelled(Message):
        """Posted on `esc`, and by a resize that drops the screen below the
        fallback threshold (research R9, FR-018) -- `message` then carries the
        fallback status text; `None` for an ordinary cancel, where the typed
        line is left exactly as it was (FR-008)."""

        def __init__(self, message: str | None = None) -> None:
            self.message = message
            super().__init__()

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        #: Fixed when the picker opens, never re-queried while it is (research
        #: R9) -- a workspace change mid-decision cannot move a row under the
        #: highlight.
        self.candidates: tuple[LinkCandidate, ...] = ()
        self.display = False

    def open(self, candidates: tuple[LinkCandidate, ...]) -> None:
        """Show the picker with `candidates`, first row highlighted."""
        self.candidates = candidates
        self.display = True
        self._rebuild_rows(select=0)

    def close(self) -> None:
        """Hide the picker and drop its candidates -- the resting state."""
        self.display = False
        self.candidates = ()
        self.clear()

    def _rebuild_rows(self, *, select: int) -> None:
        """Rebuild every row's text at the current width and leave `select`
        highlighted.

        The highlight is applied *after* the rebuild has settled, not inline.
        `clear()` resets the index to `None` and `extend()` mounts the new rows
        asynchronously, so an index assigned here lands while `ListView`'s own
        `watch_index` still has nothing it can highlight: the index takes, the
        highlight does not, and the list opens with a current row that does not
        look current -- pressing `↓` then appears to skip past the first row.
        """
        width = self.size.width
        self.clear()
        mounted = self.extend(
            _CandidateRow(candidate, render_candidate_row(candidate, width))
            for candidate in self.candidates
        )
        self.call_next(self._highlight, mounted, select)

    async def _highlight(self, mounted: AwaitMount, index: int) -> None:
        """Highlight `index` once the rows it refers to actually exist.

        Waits on the mount itself rather than on the next refresh: a refresh can
        land while the new rows are still being mounted, and `watch_index` needs
        them present to apply the highlight. A no-op if the picker closed, or
        lost its rows, while the mount was in flight.
        """
        await mounted
        if not self.display or not self._nodes:
            return
        self.index = min(index, len(self._nodes) - 1)

    def on_resize(self, event: events.Resize) -> None:
        """Keep a pending choice alive across a resize (research R9, FR-018).
        Nothing to do while closed. Below `MIN_PICKER_SCREEN_HEIGHT` the list
        is no longer usable -- cancel with the fallback message and let the
        host close the picker on the same path an ordinary `esc` already
        does. Otherwise rebuild row text at the new width and restore the
        highlighted index, which `clear()` resets to `None`."""
        if not self.display:
            return

        # Deferred to dodge a cycle: `edit_screen` imports `LinkPicker` at
        # module level, and `MIN_PICKER_SCREEN_HEIGHT` belongs there (it also
        # gates whether `_insert_link` opens the picker at all).
        from choom.tui.edit_screen import MIN_PICKER_SCREEN_HEIGHT

        if self.screen.size.height < MIN_PICKER_SCREEN_HEIGHT:
            titles = [candidate.target.title for candidate in self.candidates]
            self.post_message(self.Cancelled(link_ambiguous_status(titles)))
            return

        self._rebuild_rows(select=self.index if self.index is not None else 0)

    def action_cursor_down(self) -> None:
        """Highlight the next item, wrapping from the last row to the first
        (FR-006) -- the one line that differs from `ListView`'s own action."""
        if self.index is None:
            if self._nodes:
                self.index = 0
            return
        for index, item in loop_from_index(self._nodes, self.index, wrap=True):
            if not item.disabled:
                self.index = index
                break

    def action_cursor_up(self) -> None:
        """Highlight the previous item, wrapping from the first row to the
        last (FR-006)."""
        if self.index is None:
            if self._nodes:
                self.index = len(self._nodes) - 1
            return
        for index, item in loop_from_index(self._nodes, self.index, direction=-1, wrap=True):
            if not item.disabled:
                self.index = index
                break

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled())

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        row = event.item
        if isinstance(row, _CandidateRow):
            self.post_message(self.Chosen(row.candidate))
