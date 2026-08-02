from __future__ import annotations

from pathlib import Path

from choom.cli.main import main
from choom.core.discovery import discovery_path
from choom.core.models import Workspace
from choom.core.workspace import init_workspace
from choom.tui.app import ChoomApp
from choom.tui.status_bar import StatusBar
from tests.helpers import open_bar, type_command


def _assistant_block(config_text: str) -> str:
    """The `[assistant]` table onward -- the part that should be identical
    regardless of which adapter wrote it, ignoring the `[workspace]` block's
    per-instance `created` timestamp."""
    index = config_text.index("[assistant]")
    return config_text[index:]


async def test_cli_and_tui_produce_the_same_config_file(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    cli_root = tmp_path / "cli-workspace"
    cli_root.mkdir()
    monkeypatch.chdir(cli_root)
    main(["init"])
    capsys.readouterr()
    assert main(["config", "assistant", "claude"]) == 0
    capsys.readouterr()
    cli_config = (cli_root / ".choom" / "config.toml").read_text(encoding="utf-8")

    tui_root = tmp_path / "tui-workspace"
    tui_workspace = init_workspace(tui_root).workspace
    app = ChoomApp(tui_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await type_command(app, pilot, "config assistant claude")

    tui_config = (tui_root / ".choom" / "config.toml").read_text(encoding="utf-8")

    assert _assistant_block(cli_config) == _assistant_block(tui_config)


async def test_config_predating_this_feature_reads_without_error(
    tmp_workspace: Workspace, monkeypatch, capsys
) -> None:
    # init_workspace with no `assistant=` kwarg is exactly the shape an older
    # build would have written: no [assistant] table at all.
    config_path = tmp_workspace.root / ".choom" / "config.toml"
    assert "[assistant]" not in config_path.read_text(encoding="utf-8")

    monkeypatch.chdir(tmp_workspace.root)
    assert main(["config", "assistant"]) == 0
    out = capsys.readouterr().out
    assert "configured\t-" in out

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        bar = await open_bar(app, pilot)
        bar.value = "config assistant"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        # No crash, and the workspace opened normally.
        assert app.active == "tasks"


async def test_tui_reports_the_discovery_outcome_in_the_status_bar(
    tmp_workspace: Workspace,
) -> None:
    # 013-assistant-discovery-file, US4/T033: the TUI's peer to the CLI's stderr
    # line -- the two interfaces report the same result in their own idiom.
    from choom.core.assistants import PROFILES

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await type_command(app, pilot, "config assistant claude")

        status = app.screen.query_one(StatusBar)
        text = str(status.content)
        assert "claude" in text.lower()

    claude = next(p for p in PROFILES if p.name == "claude")
    path = discovery_path(claude)
    assert path is not None
    assert path.is_file()
