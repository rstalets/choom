from __future__ import annotations

from textual.widgets import Markdown, TextArea

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.tasks import add_task
from choom.tui.app import ChoomApp
from choom.tui.command_bar import CommandBar
from choom.tui.edit_screen import EditorPane, EditScreen
from choom.tui.list_screen import DocumentRow, ListScreen, ListView
from choom.tui.preview_screen import PreviewScreen
from choom.tui.status_bar import EDIT_HELP, StatusBar
from tests.conftest import tasks_file
from tests.helpers import create_document_out_of_process, editor_pane, list_view, to_collection

# Risk-based coverage for US1 (Principle VI): these cover what the inline
# design actually risks -- a key reaching the list, ctrl+x losing to
# TextArea's own cut, a background refresh touching the buffer, and focus
# escaping the editor. Not one test per acceptance scenario.


async def test_e_mounts_the_editor_in_the_preview_pane(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        editor_pane(app)  # asserts one is mounted
        # The rest of the screen stays exactly as it was (contract C2).
        assert app.screen.query_one("#meeting-list", ListView).display is True
        assert app.screen.query_one("#scope-pane").display is True
        assert app.screen.query_one("#collection-bar").display is True
        assert app.screen.query_one("#preview").display is False
        status = app.screen.query_one(StatusBar)
        assert EDIT_HELP in str(status.content)


async def test_list_keys_land_in_the_buffer_not_the_list(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    create_meeting(tmp_workspace, "Q4 kickoff", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        highlighted_index_before = list_view(app).index

        await pilot.press("e")
        await pilot.pause()
        editor = app.screen.query_one("#editor", TextArea)
        text_before = editor.text
        records_before = len(list_view(app).children)

        for key in ("j", "k", "e", "b", "space", "slash"):
            await pilot.press(key)
        await pilot.pause()

        # Every key landed as a literal character -- none of it reached
        # ListScreen's own bindings for the same keys (research R2).
        assert editor.text == text_before + "jkeb /"
        assert list_view(app).index == highlighted_index_before
        assert app.screen.query_one(CommandBar).display is False
        assert isinstance(app.screen, ListScreen)  # / did not open the command bar

        # ctrl+d deletes a character in the buffer, never a record.
        await pilot.press("ctrl+d")
        await pilot.pause()
        assert len(list_view(app).children) == records_before


async def test_ctrl_x_saves_and_closes_beating_text_areas_cut_binding(
    tmp_workspace: Workspace,
) -> None:
    """Canary for research R3: `EditorPane`'s `priority=True` ctrl+x binding
    must still beat `TextArea`'s own ctrl+x (cut) now that it lives on a
    widget rather than a screen. If this fails, apply R3's documented
    fallback -- move the four priority bindings to the host screens, gated by
    `check_action`, delegating to the mounted pane."""
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        highlighted = list_view(app).highlighted_child
        assert isinstance(highlighted, DocumentRow)
        selected_id = highlighted.document.id

        await pilot.press("e")
        await pilot.pause()
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "saved via ctrl+x"

        await pilot.press("ctrl+x")
        await pilot.pause()

        # A losing priority binding would have cut the current line instead
        # of saving -- the pane would still be open and the file untouched.
        assert isinstance(app.screen, ListScreen)
        assert not app.screen.query(EditorPane)
        assert "saved via ctrl+x" in meeting.path.read_text(encoding="utf-8")

        preview = app.screen.query_one("#preview", Markdown)
        assert "saved via ctrl+x" in str(preview._markdown or "")  # type: ignore[attr-defined]
        highlighted_after = list_view(app).highlighted_child
        assert isinstance(highlighted_after, DocumentRow)
        assert highlighted_after.document.id == selected_id
        assert app.screen.query_one("#meeting-list", ListView).has_focus


async def test_tab_and_shift_tab_stay_in_the_editor(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert app.active == "meetings"

        await pilot.press("e")
        await pilot.pause()
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.has_focus

        await pilot.press("tab")
        await pilot.pause()
        assert editor.has_focus
        assert app.active == "meetings"

        await pilot.press("shift+tab")
        await pilot.pause()
        assert editor.has_focus
        assert app.active == "meetings"


async def test_out_of_process_create_freezes_the_list_while_the_pane_is_open(
    tmp_workspace: Workspace,
) -> None:
    """FR-021/FR-022, research R6: a record created on disk while the inline
    editor is open does not reach the list, the buffer, or the cursor.
    Simulates the paused timer's own tick directly rather than sleeping past
    `REFRESH_SECONDS` (Principle VI, no wall-clock dependence) -- this proves
    the guard rather than the timer's scheduling. Closing shows it."""
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)
        list_screen = app.screen
        editor = app.screen.query_one("#editor", TextArea)
        text_before = editor.text
        cursor_before = editor.cursor_location
        rows_before = len(list_view(app).children)

        create_document_out_of_process(tmp_workspace, "meetings", "From outside")
        await list_screen._refresh_tick()  # what the paused timer would have run
        await pilot.pause()

        assert editor.text == text_before
        assert editor.cursor_location == cursor_before
        assert len(list_view(app).children) == rows_before
        assert editor.has_focus

        await pilot.press("escape")  # nothing typed -- closes immediately
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        assert not app.screen.query(EditorPane)
        assert len(list_view(app).children) == rows_before + 1


# --- User Story 2: task editing shares the same inline route -----------------


async def test_e_on_a_highlighted_task_edits_its_body_inline(tmp_workspace: Workspace) -> None:
    """`e` on a highlighted task edits its details in the pane (US2): the task
    list stays visible throughout, saving writes the body, and the same task
    is still highlighted afterwards with its new details in the preview."""
    add_task(tmp_workspace, "buy milk")
    task = add_task(tmp_workspace, "call the vendor")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"
        await pilot.press("j")  # highlight "call the vendor" (oldest-first order)
        await pilot.pause()

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        assert app.screen.query_one("#meeting-list", ListView).display is True
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = "Need the Q3 comparison."

        await pilot.press("ctrl+x")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        assert not app.screen.query(EditorPane)

        text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
        assert "call the vendor" in text
        assert "Need the Q3 comparison." in text

        preview = app.screen.query_one("#preview", Markdown)
        assert "Need the Q3 comparison." in str(preview._markdown or "")  # type: ignore[attr-defined]
        highlighted = list_view(app).highlighted_child
        assert highlighted.record.id == task.id  # type: ignore[union-attr]


# --- User Story 3 regression guard: full-screen reading stays full-screen ---


async def test_e_inside_preview_screen_stays_full_screen(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PreviewScreen)

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "\nedited full-screen\n"

        await pilot.press("ctrl+x")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)


# --- User Story 4: every route into edit mode from the list renders inline --


async def test_following_a_task_link_from_backlinks_opens_inline(
    tmp_workspace: Workspace,
) -> None:
    """A link in the preview that resolves to a task opens inline from the
    list screen (contract C1's last route, FR-002) -- the same route as
    `test_a_task_links_field_appears_as_an_inbound_link` in test_links.py,
    driven through the keyboard rather than `core.links` directly."""
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task = add_task(tmp_workspace, "call Terry about the renewal")
    assert task.id is not None

    text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    updated = text.replace(f"id:{task.id}", f"id:{task.id} links:{meeting.id}")
    tasks_file(tmp_workspace).write_text(updated, encoding="utf-8")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("b")  # expand backlinks -- the task links this meeting
        await pilot.pause()

        from choom.tui.links_pane import LinkRow

        links_list = app.screen.query_one("#preview-links-list", ListView)
        row_index = next(i for i, row in enumerate(links_list.children) if isinstance(row, LinkRow))
        links_list.index = row_index
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        pane = editor_pane(app)
        assert pane.target.display_path == tmp_workspace.tasks_file
