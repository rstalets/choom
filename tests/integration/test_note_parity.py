from __future__ import annotations

import asyncio
import re
from pathlib import Path

from endpaper.cli.main import main
from endpaper.core.workspace import init_workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.preview_screen import PreviewScreen

_MASKED_FIELDS = re.compile(r"^(id|created|updated):.*$", re.MULTILINE)


def _normalize(text: str) -> str:
    return _MASKED_FIELDS.sub(r"\1: <masked>", text)


async def _create_via_tui(workspace) -> Path:  # type: ignore[no-untyped-def]
    app = EndpaperApp(workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        for ch in "note.research vendor landscape #procurement":
            await pilot.press("space" if ch == " " else ch)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PreviewScreen)
        return app.screen.document.path


def test_cli_and_tui_create_note_identical_except_id_and_timestamps(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    cli_dir = tmp_path / "cli"
    cli_dir.mkdir()
    monkeypatch.chdir(cli_dir)
    main(["init"])
    capsys.readouterr()
    main(["note", "new", "vendor landscape", "--type", "research", "--tag", "procurement"])
    cli_relative_path = capsys.readouterr().out.strip()
    cli_text = (cli_dir / cli_relative_path).read_text(encoding="utf-8")

    tui_dir = tmp_path / "tui"
    tui_dir.mkdir()
    workspace = init_workspace(tui_dir)
    tui_path = asyncio.run(_create_via_tui(workspace))
    tui_text = tui_path.read_text(encoding="utf-8")

    assert _normalize(cli_text) == _normalize(tui_text)
