from __future__ import annotations

from textual.widgets import Markdown, TextArea

from choom.core.models import Workspace
from choom.core.tasks import add_task, load_tasks
from choom.tui.app import ChoomApp
from choom.tui.discard_dialog import DiscardDialog
from choom.tui.edit_screen import EditScreen
from choom.tui.list_screen import ListScreen
from tests.conftest import tasks_file, write_tasks
from tests.helpers import list_view

# --- User Story 1: reading a task's body in the preview pane (T010) ----------


def _preview_text(app: object) -> str:
    preview = app.screen.query_one("#preview", Markdown)  # type: ignore[attr-defined]
    return str(preview._markdown or "")  # type: ignore[attr-defined]


async def test_hand_written_body_renders_and_clears_on_a_body_less_task(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n"
        "\n"
        "  Need the Q3 comparison.\n"
        "\n"
        "- [ ] book the room <!-- id:t_c3d4 -->\n",
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert "call the vendor" in _preview_text(app)
        assert "Need the Q3 comparison." in _preview_text(app)

        await pilot.press("j")
        await pilot.pause()

        rendered = _preview_text(app)
        assert "book the room" in rendered
        assert "Need the Q3 comparison." not in rendered


async def test_completed_task_body_renders_the_same_way_in_done_category(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(
        tmp_workspace,
        "- [x] send the invoice <!-- id:t_c3d4 -->\n\n  Paid on the 30th.\n",
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # To-Do -> Done
        await pilot.pause()
        await pilot.press("l")
        await pilot.pause()

        rendered = _preview_text(app)
        assert "send the invoice" in rendered
        assert "Paid on the 30th." in rendered


# --- User Story 2: adding and updating a task's body via the editor (T015) ---


async def test_e_on_a_body_less_task_opens_an_empty_buffer(tmp_workspace: Workspace) -> None:
    add_task(tmp_workspace, "buy milk")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text == ""


async def test_e_on_a_task_with_a_body_opens_exactly_that_body(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  Need the Q3 comparison.\n",
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text == "Need the Q3 comparison."


async def test_save_lands_in_file_and_pane_with_same_task_highlighted(
    tmp_workspace: Workspace,
) -> None:
    add_task(tmp_workspace, "buy milk")
    task = add_task(tmp_workspace, "call the vendor")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("j")  # highlight "call the vendor" (oldest-first order)
        await pilot.pause()

        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, EditScreen)

        editor = app.screen.query_one("#editor", TextArea)
        editor.text = "Need the Q3 comparison."

        await pilot.press("ctrl+x")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
        assert "call the vendor" in text
        assert "Need the Q3 comparison." in text

        rendered = _preview_text(app)
        assert "call the vendor" in rendered
        assert "Need the Q3 comparison." in rendered

        highlighted = list_view(app).highlighted_child
        assert highlighted.record.id == task.id  # type: ignore[union-attr]


async def test_discard_leaves_tasks_file_unchanged(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call the vendor <!-- id:t_a1b2 -->\n")
    before = tasks_file(tmp_workspace).read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        editor = app.screen.query_one("#editor", TextArea)
        editor.text = "some detail I changed my mind about"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, DiscardDialog)

        dialog = app.screen
        dialog.dismiss(True)
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)

    assert tasks_file(tmp_workspace).read_bytes() == before


async def test_no_op_save_leaves_the_file_byte_identical(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  Need the Q3 comparison.\n",
    )
    before = tasks_file(tmp_workspace).read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        await pilot.press("ctrl+x")
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)

    assert tasks_file(tmp_workspace).read_bytes() == before


# --- User Story 2 scenario 7: toggling done preserves the body (T016) --------


async def test_toggling_done_preserves_the_body(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  Need the Q3 comparison.\n",
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

    text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    assert "- [x] call the vendor <!-- id:t_a1b2 -->" in text
    assert "Need the Q3 comparison." in text

    tasks, _warnings = load_tasks(tmp_workspace)
    assert tasks[0].done is True
    assert tasks[0].body == "Need the Q3 comparison."
