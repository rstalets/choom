from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, ListItem, ListView

from choom.core.models import YearMonth

CATEGORY_LABELS = {"todo": "To-Do", "done": "Done"}


class MonthRow(ListItem):
    def __init__(self, month: YearMonth) -> None:
        super().__init__(Label(str(month)))
        self.month = month


class UnfiledRow(ListItem):
    def __init__(self) -> None:
        super().__init__(Label("Unfiled"))


class CategoryRow(ListItem):
    def __init__(self, category: str) -> None:
        super().__init__(Label(CATEGORY_LABELS[category]))
        self.category = category


class SearchingRow(ListItem):
    def __init__(self) -> None:
        super().__init__(Label("Searching…"))


class SuspendedRow(ListItem):
    def __init__(self) -> None:
        super().__init__(Label("(filtered)"))


class ScopePane(Vertical):
    """The left pane: months (+ Unfiled) for Notes/Meetings, To-Do/Done for Tasks."""

    def compose(self) -> ComposeResult:
        yield ListView(id="scope-list")

    async def show_months(
        self,
        months: tuple[YearMonth, ...],
        *,
        has_unfiled: bool,
        highlight: YearMonth | str,
    ) -> None:
        list_view = self.query_one("#scope-list", ListView)
        await list_view.clear()
        rows: list[ListItem] = [MonthRow(m) for m in months]
        if has_unfiled:
            rows.append(UnfiledRow())
        await list_view.extend(rows)

        index = 0
        for i, row in enumerate(rows):
            if isinstance(row, MonthRow) and row.month == highlight:
                index = i
                break
            if isinstance(row, UnfiledRow) and highlight == "unfiled":
                index = i
                break
        list_view.index = index

    async def show_categories(self, *, highlight: str) -> None:
        list_view = self.query_one("#scope-list", ListView)
        await list_view.clear()
        rows = [CategoryRow("todo"), CategoryRow("done")]
        await list_view.extend(rows)
        list_view.index = 0 if highlight == "todo" else 1

    async def show_suspended(self, *, loading: bool) -> None:
        """A cross-month filter is active: the scope pane no longer reflects one
        month, and shows a loading row while the once-per-session load runs."""
        list_view = self.query_one("#scope-list", ListView)
        await list_view.clear()
        await list_view.extend([SearchingRow() if loading else SuspendedRow()])
