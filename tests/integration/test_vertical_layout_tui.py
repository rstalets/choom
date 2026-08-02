"""020-vertical-tui-mode: the layout switch, what survives it, persistence,
parity with horizontal, the resize guard, terminal-size boundaries, and the
command's error/report wording.

One file, filtered by `-k` per task, per plan.md's Project Structure and
tasks.md's phase-3-through-7 verify commands.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from textual.widgets import ListView

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.preferences import get_view_orientation, set_view_orientation
from choom.tui.app import ChoomApp
from choom.tui.list_screen import DocumentRow, ListScreen
from tests.helpers import list_view, to_collection, type_command

# --- T012/T013/T015 (US1): the switch itself, and what it preserves --------


async def test_config_view_vertical_sets_and_persists(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await type_command(app, pilot, "config view vertical")
        assert app.view_orientation == "vertical"
        assert get_view_orientation() == "vertical"


async def test_config_view_vertical_reports_confirmation(tmp_workspace: Workspace) -> None:
    from choom.tui.status_bar import StatusBar

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await type_command(app, pilot, "config view vertical")
        status = str(app.screen.query_one(StatusBar).content)
        assert "view set to vertical" in status


async def test_vertical_tree_groups_scope_and_list_above_preview(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "config view vertical")

        upper_band = app.screen.query_one("#upper-band")
        scope_pane = app.screen.query_one("#scope-pane")
        list_pane = app.screen.query_one("#list-pane")
        preview_pane = app.screen.query_one("#preview-pane")

        assert scope_pane in upper_band.children
        assert list_pane in upper_band.children
        assert preview_pane not in upper_band.children
        body = app.screen.query_one("#body")
        assert upper_band in body.children
        assert preview_pane in body.children


async def test_horizontal_tree_has_all_three_as_siblings_of_body(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        body = app.screen.query_one("#body")
        assert app.screen.query_one("#scope-pane") in body.children
        assert app.screen.query_one("#list-pane") in body.children
        assert app.screen.query_one("#preview-pane") in body.children
        assert not app.screen.query("#upper-band")


async def test_switch_preserves_highlighted_record_and_preview(
    tmp_workspace: Workspace,
) -> None:
    from textual.widgets import Markdown

    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    create_meeting(tmp_workspace, "Q4 kickoff", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        highlighted_before = list_view(app).highlighted_child
        assert isinstance(highlighted_before, DocumentRow)
        selected_id = highlighted_before.document.id
        selected_title = highlighted_before.document.title

        await type_command(app, pilot, "config view vertical")

        highlighted_after = list_view(app).highlighted_child
        assert isinstance(highlighted_after, DocumentRow)
        assert highlighted_after.document.id == selected_id

        preview = app.screen.query_one("#preview", Markdown)
        assert selected_title in str(preview._markdown or "")  # type: ignore[attr-defined]


async def test_switch_preserves_collection_scope_and_filter(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "filter Q3")
        assert app.filter_query == "Q3"

        await type_command(app, pilot, "config view vertical")

        assert app.active == "meetings"
        assert app.filter_query == "Q3"


async def test_switch_focuses_the_record_list(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "config view vertical")
        assert app.screen.query_one("#meeting-list", ListView).has_focus


async def test_h_and_l_still_move_between_scope_pane_and_list_in_vertical(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "config view vertical")

        await pilot.press("h")
        await pilot.pause()
        assert app.screen.query_one("#scope-list", ListView).has_focus

        await pilot.press("l")
        await pilot.pause()
        assert app.screen.query_one("#meeting-list", ListView).has_focus


async def test_record_list_is_wider_in_vertical_than_horizontal_at_same_size(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    horizontal_app = ChoomApp(tmp_workspace)
    async with horizontal_app.run_test(size=(120, 40)) as pilot:
        await to_collection(horizontal_app, pilot, "meetings")
        horizontal_width = horizontal_app.screen.query_one("#list-pane").size.width

    set_view_orientation("vertical")
    vertical_app = ChoomApp(tmp_workspace)
    async with vertical_app.run_test(size=(120, 40)) as pilot:
        await to_collection(vertical_app, pilot, "meetings")
        vertical_width = vertical_app.screen.query_one("#list-pane").size.width

    assert vertical_width > horizontal_width


# --- T014: the backlinks-expanded state survives a switch -------------------


async def test_backlinks_survive_a_switch_to_vertical(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("b")
        await pilot.pause()
        assert app.screen.query_one("#preview-links-section").display is True

        await type_command(app, pilot, "config view vertical")

        assert app.screen._preview_links_expanded is True  # type: ignore[attr-defined]
        assert app.screen.query_one("#preview-links-section").display is True


async def test_backlinks_collapsed_stays_collapsed_after_a_switch(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert app.screen.query_one("#preview-links-section").display is False

        await type_command(app, pilot, "config view vertical")

        assert app.screen.query_one("#preview-links-section").display is False


async def test_setting_to_the_value_already_in_effect_does_not_rearrange(
    tmp_workspace: Workspace,
) -> None:
    """Contract C3's idempotence clause: rearranges nothing and reports the
    same confirmation."""
    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert not isinstance(app.screen, type(None))
        assert not app.screen.query("#upper-band")

        await type_command(app, pilot, "config view horizontal")

        assert not app.screen.query("#upper-band")
        assert isinstance(app.screen, ListScreen)


# --- T016 (US2): the preference is remembered, and it is per-user, not per-
# workspace -------------------------------------------------------------------


async def test_persist_fresh_app_with_stored_vertical_opens_vertical(
    tmp_workspace: Workspace,
) -> None:
    set_view_orientation("vertical")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.screen.query("#upper-band")


async def test_persist_fresh_app_with_no_preferences_file_opens_horizontal(
    tmp_workspace: Workspace,
) -> None:
    assert get_view_orientation() == "horizontal"  # FR-002: no config needed
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert not app.screen.query("#upper-band")


async def test_persist_stored_preference_applies_in_a_second_unrelated_workspace(
    tmp_path: Path,
) -> None:
    from choom.core.workspace import init_workspace

    set_view_orientation("vertical")

    workspace_one = init_workspace(tmp_path / "one").workspace
    app_one = ChoomApp(workspace_one)
    async with app_one.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app_one.screen.query("#upper-band")

    workspace_two = init_workspace(tmp_path / "two").workspace
    app_two = ChoomApp(workspace_two)
    async with app_two.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app_two.screen.query("#upper-band")


# --- T017 (US2): a switch writes nothing inside the workspace (FR-024, SC-005)


def _snapshot(root):  # type: ignore[no-untyped-def]
    return {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


async def test_workspace_untouched_switch_writes_nothing_inside_it(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")
    before = _snapshot(tmp_workspace.root)

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "config view vertical")

    after = _snapshot(tmp_workspace.root)
    assert before == after


async def test_workspace_untouched_switch_adds_no_view_table_to_config(
    tmp_workspace: Workspace,
) -> None:
    config_path = tmp_workspace.root / ".choom" / "config.toml"
    before = config_path.read_text(encoding="utf-8")
    assert "[view]" not in before

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await type_command(app, pilot, "config view vertical")

    after = config_path.read_text(encoding="utf-8")
    assert after == before
    assert "[view]" not in after


# --- T018 (US3): the inline editor opens in the lower band in vertical -----


async def test_inline_editor_opens_in_the_lower_band_with_list_and_scope_visible(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.edit_screen import EditorPane
    from choom.tui.status_bar import EDIT_HELP, StatusBar

    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "config view vertical")

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        app.screen.query_one(EditorPane)  # mounted, and inside #preview-pane
        preview_pane = app.screen.query_one("#preview-pane")
        assert preview_pane.query_one(EditorPane)
        # The list and scope pane, in the upper band, stay visible throughout.
        assert app.screen.query_one("#scope-pane").display is True
        assert app.screen.query_one("#meeting-list", ListView).display is True
        assert app.screen.query_one("#collection-bar").display is True
        status = app.screen.query_one(StatusBar)
        assert EDIT_HELP in str(status.content)


async def test_inline_editor_saves_identically_in_vertical(tmp_workspace: Workspace) -> None:
    from textual.widgets import Markdown, TextArea

    from choom.tui.edit_screen import EditorPane

    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "config view vertical")
        highlighted = list_view(app).highlighted_child
        assert isinstance(highlighted, DocumentRow)
        selected_id = highlighted.document.id

        await pilot.press("e")
        await pilot.pause()
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "saved via vertical layout"

        await pilot.press("ctrl+x")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        assert not app.screen.query(EditorPane)
        assert "saved via vertical layout" in meeting.path.read_text(encoding="utf-8")
        preview = app.screen.query_one("#preview", Markdown)
        assert "saved via vertical layout" in str(preview._markdown or "")  # type: ignore[attr-defined]
        highlighted_after = list_view(app).highlighted_child
        assert isinstance(highlighted_after, DocumentRow)
        assert highlighted_after.document.id == selected_id


async def test_inline_editor_discards_identically_in_vertical(tmp_workspace: Workspace) -> None:
    from textual.widgets import TextArea

    from choom.tui.edit_screen import EditorPane

    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    original = meeting.path.read_text(encoding="utf-8")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "config view vertical")

        await pilot.press("e")
        await pilot.pause()
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "discard me"

        # A dirty editor's `escape` raises the discard confirmation
        # (test_discard_tui.py's established pattern); `enter` confirms.
        await pilot.press("escape")
        await pilot.pause()
        from choom.tui.confirm_dialog import ConfirmDialog

        assert isinstance(app.screen, ConfirmDialog)
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        assert not app.screen.query(EditorPane)
        assert meeting.path.read_text(encoding="utf-8") == original


# --- T019 (US3, FR-043): the backlinks section cannot swallow the lower band


async def test_backlinks_expanded_at_80x24_still_leaves_preview_content_visible(
    tmp_workspace: Workspace,
) -> None:
    """Regression guard: the old fixed `max-height: 12` would consume the
    *entire* lower band at 80x24 in vertical (~10 rows), leaving nothing of
    the preview visible above the backlinks section. The vertical variant
    bounds it as a fraction of the band instead.

    Needs enough inbound links to actually fill `#preview-links-list`'s own
    (unchanged) `max-height: 10` -- with only a couple of backlinks, the
    rendered section is small regardless of which cap governs it, and the
    two caps would look identical."""
    from choom.core.notes import create_note

    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    for i in range(15):
        note = create_note(tmp_workspace, f"linking note {i}")
        note.path.write_text(
            note.path.read_text(encoding="utf-8") + f"\nSee [Q3 planning](#{meeting.id}).\n",
            encoding="utf-8",
        )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "config view vertical")

        await pilot.press("b")
        await pilot.pause()

        preview_pane = app.screen.query_one("#preview-pane")
        links_section = app.screen.query_one("#preview-links-section")
        assert links_section.display is True
        # The regression this guards against: the old fixed `max-height: 12`
        # would consume the *entire* ~10-row band, leaving zero rows of the
        # pane visible above it. The fraction-based bound must leave a real,
        # nonzero slice of the band for the preview content that sits above
        # the backlinks section (Markdown's own `.size` reflects its full,
        # scrollable content height, not the visible viewport, so the
        # meaningful assertion is about the *pane*, not the widget inside it).
        assert links_section.size.height > 0
        assert links_section.size.height < preview_pane.size.height


# --- T020 (US3, FR-027/FR-028): bindings and footer text are identical -----
# between orientations; only pane geometry differs.


async def _footer_text(app: ChoomApp) -> str:
    from choom.tui.status_bar import StatusBar

    return str(app.screen.query_one(StatusBar).content)


async def test_parity_footer_text_identical_in_list_state(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    horizontal_app = ChoomApp(tmp_workspace)
    async with horizontal_app.run_test(size=(120, 40)) as pilot:
        await to_collection(horizontal_app, pilot, "meetings")
        horizontal_footer = await _footer_text(horizontal_app)

    set_view_orientation("vertical")
    vertical_app = ChoomApp(tmp_workspace)
    async with vertical_app.run_test(size=(120, 40)) as pilot:
        await to_collection(vertical_app, pilot, "meetings")
        vertical_footer = await _footer_text(vertical_app)

    assert horizontal_footer == vertical_footer
    assert "vertical" not in horizontal_footer.lower()
    assert "horizontal" not in horizontal_footer.lower()


async def test_parity_footer_text_identical_in_task_list_state(
    tmp_workspace: Workspace,
) -> None:
    horizontal_app = ChoomApp(tmp_workspace)
    async with horizontal_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        horizontal_footer = await _footer_text(horizontal_app)

    set_view_orientation("vertical")
    vertical_app = ChoomApp(tmp_workspace)
    async with vertical_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        vertical_footer = await _footer_text(vertical_app)

    assert horizontal_footer == vertical_footer


async def test_parity_footer_text_identical_with_backlinks_focused(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    horizontal_app = ChoomApp(tmp_workspace)
    async with horizontal_app.run_test(size=(120, 40)) as pilot:
        await to_collection(horizontal_app, pilot, "meetings")
        await pilot.press("b")
        await pilot.pause()
        horizontal_footer = await _footer_text(horizontal_app)

    set_view_orientation("vertical")
    vertical_app = ChoomApp(tmp_workspace)
    async with vertical_app.run_test(size=(120, 40)) as pilot:
        await to_collection(vertical_app, pilot, "meetings")
        await pilot.press("b")
        await pilot.pause()
        vertical_footer = await _footer_text(vertical_app)

    assert horizontal_footer == vertical_footer


async def test_parity_footer_text_identical_with_inline_editor_open(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    horizontal_app = ChoomApp(tmp_workspace)
    async with horizontal_app.run_test(size=(120, 40)) as pilot:
        await to_collection(horizontal_app, pilot, "meetings")
        await pilot.press("e")
        await pilot.pause()
        horizontal_footer = await _footer_text(horizontal_app)

    set_view_orientation("vertical")
    vertical_app = ChoomApp(tmp_workspace)
    async with vertical_app.run_test(size=(120, 40)) as pilot:
        await to_collection(vertical_app, pilot, "meetings")
        await pilot.press("e")
        await pilot.pause()
        vertical_footer = await _footer_text(vertical_app)

    assert horizontal_footer == vertical_footer


async def test_parity_footer_text_identical_in_preview_screen(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    horizontal_app = ChoomApp(tmp_workspace)
    async with horizontal_app.run_test(size=(120, 40)) as pilot:
        await to_collection(horizontal_app, pilot, "meetings")
        await pilot.press("enter")
        await pilot.pause()
        horizontal_footer = str(horizontal_app.screen.query_one("StatusBar").content)  # type: ignore[attr-defined]

    set_view_orientation("vertical")
    vertical_app = ChoomApp(tmp_workspace)
    async with vertical_app.run_test(size=(120, 40)) as pilot:
        await to_collection(vertical_app, pilot, "meetings")
        await pilot.press("enter")
        await pilot.pause()
        vertical_footer = str(vertical_app.screen.query_one("StatusBar").content)  # type: ignore[attr-defined]

    assert horizontal_footer == vertical_footer


async def test_parity_full_screen_preview_takes_the_whole_window_and_returns(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.preview_screen import PreviewScreen

    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "config view vertical")
        assert app.screen.query("#upper-band")

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PreviewScreen)
        # Full-screen: not scoped by #upper-band/#body at all.
        assert not app.screen.query("#upper-band")
        assert app.screen.size == app.size

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)
        assert app.screen.query("#upper-band")  # returned to the configured layout


async def test_parity_full_screen_editor_takes_the_whole_window_and_returns(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.edit_screen import EditScreen
    from choom.tui.preview_screen import PreviewScreen

    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "config view vertical")

        await pilot.press("enter")  # list -> full-screen preview
        await pilot.pause()
        await pilot.press("e")  # preview -> full-screen editor
        await pilot.pause()
        assert isinstance(app.screen, EditScreen)
        assert not app.screen.query("#upper-band")
        assert app.screen.size == app.size

        await pilot.press("ctrl+x")  # save & back -- to the preview it was opened from
        await pilot.pause()
        assert isinstance(app.screen, PreviewScreen)

        await pilot.press("escape")  # back to the list
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)
        assert app.screen.query("#upper-band")  # still the configured layout


# --- T021 (US4, contracts/tui.md C4): the resize path ----------------------


async def test_resize_crossing_the_threshold_with_no_editor_flips_the_layout(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.layout import MIN_VERTICAL_SCREEN_HEIGHT

    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, MIN_VERTICAL_SCREEN_HEIGHT + 5)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert app.screen.query("#upper-band")

        await pilot.resize_terminal(80, MIN_VERTICAL_SCREEN_HEIGHT - 1)
        await pilot.pause()

        assert not app.screen.query("#upper-band")  # fell back to horizontal


async def test_resize_not_crossing_the_threshold_does_not_flip(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.layout import MIN_VERTICAL_SCREEN_HEIGHT

    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, MIN_VERTICAL_SCREEN_HEIGHT + 10)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert app.screen.query("#upper-band")

        await pilot.resize_terminal(80, MIN_VERTICAL_SCREEN_HEIGHT + 3)
        await pilot.pause()

        assert app.screen.query("#upper-band")  # still comfortably vertical


async def test_resize_growing_back_above_threshold_restores_vertical(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.layout import MIN_VERTICAL_SCREEN_HEIGHT

    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, MIN_VERTICAL_SCREEN_HEIGHT - 1)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert not app.screen.query("#upper-band")  # started below the floor

        await pilot.resize_terminal(80, MIN_VERTICAL_SCREEN_HEIGHT + 5)
        await pilot.pause()

        assert app.screen.query("#upper-band")


# --- T022 (US4): the data-loss regression test, and proof the guard is
# load-bearing. See "The one way this feature loses the user's words" in
# tasks.md -- this is the only path in the feature that can destroy the
# user's typed-but-unsaved words, and a guard whose test would pass without
# it is not a guard.


async def test_dirty_editor_survives_a_resize_crossing_the_threshold(
    tmp_workspace: Workspace,
) -> None:
    """FR-025: open the inline editor in vertical, type text without
    saving, resize below `MIN_VERTICAL_SCREEN_HEIGHT` and back, and confirm
    the editor is still mounted, still focused, and still holds the typed
    text byte-for-byte.

    Without the guard (`ListScreen.on_resize`'s branch one), the resize
    below the threshold would call `Widget.recompose()` on `#body`, which
    tears down and rebuilds all of `#body`'s children -- including the
    `EditorPane` mounted inside `#preview-pane` -- discarding the unsaved
    buffer with no confirmation and no way to recover it. This was
    confirmed by hand during implementation: commenting out branch one of
    `on_resize`'s guard makes this test fail with the editor gone
    (`app.screen.query(EditorPane)` empty) and the typed text lost -- the
    observed failure mode is exactly "the pane vanishes, unsaved text and
    all," not an exception. The guard was restored before this test was
    committed.
    """
    from textual.widgets import TextArea

    from choom.tui.edit_screen import EditorPane
    from choom.tui.layout import MIN_VERTICAL_SCREEN_HEIGHT

    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, MIN_VERTICAL_SCREEN_HEIGHT + 10)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert app.screen.query("#upper-band")

        await pilot.press("e")
        await pilot.pause()
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved words that must survive a resize"
        expected_text = editor.text

        await pilot.resize_terminal(80, MIN_VERTICAL_SCREEN_HEIGHT - 1)
        await pilot.pause()
        await pilot.resize_terminal(80, MIN_VERTICAL_SCREEN_HEIGHT + 10)
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        panes = app.screen.query(EditorPane)
        assert len(panes) == 1
        editor_after = panes[0].query_one("#editor", TextArea)
        assert editor_after.text == expected_text
        assert editor_after.has_focus


# --- T023 (US4): the threshold boundary, in both directions ----------------


async def test_boundary_at_exactly_eleven_rows_renders_vertical_at_minimum(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.layout import MIN_VERTICAL_SCREEN_HEIGHT

    assert MIN_VERTICAL_SCREEN_HEIGHT == 11
    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning")
    create_meeting(tmp_workspace, "Q4 kickoff")
    create_meeting(tmp_workspace, "Q1 review")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, MIN_VERTICAL_SCREEN_HEIGHT)) as pilot:
        await to_collection(app, pilot, "meetings")

        assert app.screen.query("#upper-band")
        list_view_widget = app.screen.query_one("#meeting-list", ListView)
        header = app.screen.query_one("#list-header")
        # Column header (1) + at least 3 record rows above it.
        assert header.size.height >= 1
        assert len(list_view_widget.children) >= 3
        preview_pane = app.screen.query_one("#preview-pane")
        assert preview_pane.size.height >= 4


async def test_boundary_at_ten_rows_renders_horizontal(tmp_workspace: Workspace) -> None:
    from choom.tui.layout import MIN_VERTICAL_SCREEN_HEIGHT

    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, MIN_VERTICAL_SCREEN_HEIGHT - 1)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert not app.screen.query("#upper-band")


async def test_boundary_resize_ten_to_eleven_restores_vertical_with_nothing_typed(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.layout import MIN_VERTICAL_SCREEN_HEIGHT

    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, MIN_VERTICAL_SCREEN_HEIGHT - 1)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert not app.screen.query("#upper-band")

        await pilot.resize_terminal(80, MIN_VERTICAL_SCREEN_HEIGHT)
        await pilot.pause()

        assert app.screen.query("#upper-band")  # FR-033: restored, nothing typed


async def test_boundary_round_trip_24_to_10_to_24_leaves_stored_preference_unchanged(
    tmp_workspace: Workspace,
) -> None:
    """FR-034: degrading to horizontal (and back) must never rewrite the
    stored preference -- it reads "vertical" throughout the round trip."""
    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert app.screen.query("#upper-band")
        assert get_view_orientation() == "vertical"

        await pilot.resize_terminal(80, 10)
        await pilot.pause()
        assert not app.screen.query("#upper-band")
        assert get_view_orientation() == "vertical"  # unchanged by the fallback

        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert app.screen.query("#upper-band")
        assert get_view_orientation() == "vertical"  # still unchanged


# --- T024 (US4, FR-031, SC-008): the required 80x24 case; 120x40 companion -


async def test_terminal_size_80x24_vertical_is_usable(tmp_workspace: Workspace) -> None:
    """No test in the repo previously exercised height at all -- the
    existing narrow-terminal tests (test_narrow_terminal_tui.py) all vary
    *width* at a fixed 24 rows. This is genuinely new coverage."""
    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning")
    create_meeting(tmp_workspace, "Q4 kickoff")
    create_meeting(tmp_workspace, "Q1 review")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")

        assert app.screen.query("#upper-band")
        header = app.screen.query_one("#list-header")
        list_view_widget = app.screen.query_one("#meeting-list", ListView)
        preview_pane = app.screen.query_one("#preview-pane")

        assert header.size.height >= 1
        assert len(list_view_widget.children) >= 3
        assert preview_pane.size.height >= 4
        # Neither band is reduced to a single row.
        upper_band = app.screen.query_one("#upper-band")
        assert upper_band.size.height > 1
        assert preview_pane.size.height > 1


async def test_terminal_size_120x40_vertical_is_comfortable(tmp_workspace: Workspace) -> None:
    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await to_collection(app, pilot, "meetings")

        assert app.screen.query("#upper-band")
        upper_band = app.screen.query_one("#upper-band")
        preview_pane = app.screen.query_one("#preview-pane")
        assert upper_band.size.height > 10
        assert preview_pane.size.height > 10


# --- T026 (US5, FR-044/FR-045): error messages name what went wrong and what
# to do instead --------------------------------------------------------------


async def test_error_illegal_view_value_names_value_and_accepted(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.status_bar import StatusBar

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await type_command(app, pilot, "config view sideways")
        status = str(app.screen.query_one(StatusBar).content)
        assert "view must be one of horizontal, vertical; got 'sideways'" in status
        assert not app.screen.query("#upper-band")  # layout unchanged


async def test_error_illegal_view_value_writes_nothing(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await type_command(app, pilot, "config view sideways")
    assert get_view_orientation() == "horizontal"  # nothing was ever written


async def test_error_unknown_setting_names_the_settings_that_exist(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.status_bar import StatusBar

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await type_command(app, pilot, "config layout vertical")
        status = str(app.screen.query_one(StatusBar).content)
        assert "unknown setting: 'layout'; known settings: assistant, view" in status


# --- T027 (US5, FR-037/FR-038): the get form and the fallback report -------


async def test_report_get_form_when_unset_names_default_and_accepted(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.status_bar import StatusBar

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await type_command(app, pilot, "config view")
        status = str(app.screen.query_one(StatusBar).content)
        assert "view: horizontal (default); accepted: horizontal, vertical" in status


async def test_report_get_form_when_set_names_the_stored_value(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.status_bar import StatusBar

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await type_command(app, pilot, "config view vertical")
        await type_command(app, pilot, "config view")
        status = str(app.screen.query_one(StatusBar).content)
        assert "view: vertical; accepted: horizontal, vertical" in status


async def test_report_get_form_names_both_facts_when_fallback_in_effect(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.layout import MIN_VERTICAL_SCREEN_HEIGHT
    from choom.tui.status_bar import StatusBar

    set_view_orientation("vertical")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, MIN_VERTICAL_SCREEN_HEIGHT - 1)) as pilot:
        await type_command(app, pilot, "config view")
        status = str(app.screen.query_one(StatusBar).content)
        assert (
            "view: vertical, but horizontal is in effect — the terminal is too "
            "short; accepted: horizontal, vertical"
        ) in status


async def test_report_setting_vertical_on_a_too_short_terminal_still_saves_and_says_so(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.layout import MIN_VERTICAL_SCREEN_HEIGHT
    from choom.tui.status_bar import StatusBar

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, MIN_VERTICAL_SCREEN_HEIGHT - 1)) as pilot:
        await type_command(app, pilot, "config view vertical")
        status = str(app.screen.query_one(StatusBar).content)
        assert (
            f"view set to vertical; terminal is too short — horizontal is in "
            f"effect until it is at least {MIN_VERTICAL_SCREEN_HEIGHT} rows tall"
        ) in status
    # FR-038: still saves, even though horizontal is what actually renders.
    assert get_view_orientation() == "vertical"


# --- T029 (US5, FR-013): a store failure degrades to a session-only switch,
# not an aborted interface -----------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="chmod-based permission simulation is POSIX-only")
async def test_unwritable_preferences_directory_still_switches_for_the_session(
    tmp_workspace: Workspace,
    _isolated_profile_and_preferences_roots: Path,
) -> None:
    import stat

    root = _isolated_profile_and_preferences_roots
    root.chmod(stat.S_IREAD | stat.S_IEXEC)
    try:
        app = ChoomApp(tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await type_command(app, pilot, "config view vertical")

            # The layout still switched for this session (FR-013) -- a
            # failed write must not abort the interface.
            assert app.screen.query("#upper-band")
            assert app.view_orientation == "vertical"

            from choom.tui.status_bar import StatusBar

            status = str(app.screen.query_one(StatusBar).content)
            assert "view set to vertical for this session; could not save the preference:" in (
                status
            )
    finally:
        root.chmod(stat.S_IRWXU)
