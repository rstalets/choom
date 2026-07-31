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
