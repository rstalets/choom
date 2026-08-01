from __future__ import annotations

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin


def test_generated_tasks_file_parses_as_commonmark_task_list(cli) -> None:
    cli(
        "task",
        "add",
        "send the vendor comparison",
        "--type",
        "followup",
        "--tag",
        "procurement",
    )
    cli("task", "add", "book the room")

    text = cli.read("tasks.md")

    md = MarkdownIt("commonmark").use(tasklists_plugin)
    tokens = md.parse(text)

    list_item_tokens = [t for t in tokens if t.type == "list_item_open"]
    assert len(list_item_tokens) == 2

    rendered = md.render(text)
    # A real markdown checkbox, recognized by the task-list convention every
    # renderer (GitHub, Obsidian, VS Code) implements on top of CommonMark.
    assert rendered.count('type="checkbox"') == 2
    assert "send the vendor comparison" in rendered
    assert "book the room" in rendered
    # The metadata rides in a syntactically valid HTML comment -- invisible when
    # a browser or markdown viewer renders the DOM, even though it is present in
    # the HTML source (which is what "invisible in rendered output" means).
    assert "<!--" in rendered
    assert "-->" in rendered


def test_tasks_file_with_bodies_renders_as_a_nested_checklist(cli) -> None:
    """SC-008: a tasks.md containing bodies still renders as a correct nested
    checklist in a markdown viewer that knows nothing about choom."""
    cli("task", "add", "call the vendor", "--type", "followup", "--tag", "procurement")
    cli("task", "add", "book the room")

    tasks_path = cli.root / "tasks.md"
    text = tasks_path.read_text(encoding="utf-8")
    task_id = text.split("id:")[1].split()[0]
    text += "\n  Need the Q3 comparison.\n\n  - 07-28 called, left voicemail\n"
    tasks_path.write_text(text, encoding="utf-8")

    md = MarkdownIt("commonmark").use(tasklists_plugin)
    tokens = md.parse(text)

    list_item_tokens = [t for t in tokens if t.type == "list_item_open"]
    # Two top-level tasks, plus the nested bullet inside the first one's body.
    assert len(list_item_tokens) == 3

    rendered = md.render(text)
    assert rendered.count('type="checkbox"') == 2
    assert "Need the Q3 comparison." in rendered
    assert "07-28 called, left voicemail" in rendered
    assert task_id in text  # the body sits directly under its own task's id
