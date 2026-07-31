from __future__ import annotations

import asyncio
from pathlib import Path

from endpaper.cli.main import main
from endpaper.core.workspace import init_workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListView, TaskRow

_SEED = "- [ ] send the vendor comparison <!-- id:t_a1b2 type:followup created:2026-07-28 -->\n"


async def _toggle_via_tui(workspace) -> None:  # type: ignore[no-untyped-def]
    app = EndpaperApp(workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert isinstance(list_view.highlighted_child, TaskRow)
        await pilot.press("space")
        await pilot.pause()


def test_cli_and_tui_toggle_produce_byte_identical_files(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    cli_dir = tmp_path / "cli"
    cli_dir.mkdir()
    monkeypatch.chdir(cli_dir)
    main(["init"])
    capsys.readouterr()
    (cli_dir / "tasks.md").write_text(_SEED, encoding="utf-8", newline="\n")

    main(["task", "done", "t_a1b2"])
    capsys.readouterr()
    cli_text = (cli_dir / "tasks.md").read_text(encoding="utf-8")

    tui_dir = tmp_path / "tui"
    workspace = init_workspace(tui_dir).workspace
    workspace.tasks_file.write_text(_SEED, encoding="utf-8", newline="\n")

    asyncio.run(_toggle_via_tui(workspace))
    tui_text = workspace.tasks_file.read_text(encoding="utf-8")

    assert tui_text == cli_text
    assert "[x]" in tui_text
