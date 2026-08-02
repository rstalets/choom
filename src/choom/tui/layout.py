"""Vertical-layout geometry (020-vertical-tui-mode): the effective-orientation
decision and the threshold it is measured against.

Pure functions and constants, no widget imports, so the geometry is
unit-testable without a terminal -- the arrangement `columns.py` already
established for layout arithmetic (research R8): this is interface code that
happens to be pure, not `core` logic, because `core` has no notion of a
screen.
"""

from __future__ import annotations

COLLECTION_BAR_ROWS = 1  # app.tcss: CollectionBar { dock: top; height: 1 }
STATUS_BAR_ROWS = 1  # app.tcss: StatusBar { height: 1 }
BAND_DIVIDER_ROWS = 1  # border-top on the lower band
MIN_UPPER_BAND_ROWS = 4  # #list-header (1) + 3 record rows        (FR-032)
MIN_LOWER_BAND_ROWS = 4  # 4 lines of preview content              (FR-032)

#: Written as the sum of the five constants above, never as the literal
#: `11` -- the number is a consequence of five stated minimums, and writing
#: it as a literal is how it becomes untouchable in six months when someone
#: needs to know whether it can move and what it would break.
MIN_VERTICAL_SCREEN_HEIGHT = (
    COLLECTION_BAR_ROWS
    + STATUS_BAR_ROWS
    + BAND_DIVIDER_ROWS
    + MIN_UPPER_BAND_ROWS
    + MIN_LOWER_BAND_ROWS
)  # == 11


def effective_orientation(stored: str, screen_height: int) -> str:
    """The orientation actually rendered, resolving `stored` against the
    terminal's current total height.

    Deliberately **not** a function of terminal width (FR-035, FR-039) --
    width degradation is already handled identically in both orientations by
    `column_widths`, `CollectionBar._render_bar`, and `shorten_workspace_path`
    -- nor of *available* body height (FR-035): the command bar, the link
    picker, and the backlinks section all shrink the body when opened, and
    reading available height would flip the whole layout underneath the user
    mid-keystroke. Whether an editor is open is not an input either -- the
    editor must not change this answer, only suppress *acting* on a changed
    one; that guard lives in the resize handler, not here.

    Never raises. An unrecognised `stored` value returns `"horizontal"`.
    """
    if stored == "vertical" and screen_height < MIN_VERTICAL_SCREEN_HEIGHT:
        return "horizontal"
    if stored == "vertical":
        return "vertical"
    return "horizontal"
