from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin

from endpaper.cli.main import main


def test_generated_tasks_file_parses_as_commonmark_task_list(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(
        [
            "task",
            "add",
            "send the vendor comparison",
            "--type",
            "followup",
            "--tag",
            "procurement",
        ]
    )
    capsys.readouterr()
    main(["task", "add", "book the room"])
    capsys.readouterr()

    text = (tmp_path / "tasks.md").read_text(encoding="utf-8")

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
