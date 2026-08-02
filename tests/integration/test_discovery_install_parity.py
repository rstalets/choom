"""US1 end-to-end: setting the assistant from either adapter installs the same
discovery file (013-assistant-discovery-file, tasks.md T017). Parametrized across the
CLI and TUI rather than duplicated into two files (constitution VI)."""

from __future__ import annotations

from pathlib import Path

import pytest

from choom.cli.main import main
from choom.core.assistants import PROFILES
from choom.core.discovery import discovery_path
from choom.core.models import Workspace
from choom.core.workspace import init_workspace
from choom.tui.app import ChoomApp
from tests.helpers import type_command

_CLAUDE = next(p for p in PROFILES if p.name == "claude")


async def _install_via_cli(workspace: Workspace, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(workspace.root)
    assert main(["config", "assistant", "claude"]) == 0


async def _install_via_tui(workspace: Workspace, monkeypatch: pytest.MonkeyPatch) -> None:
    app = ChoomApp(workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await type_command(app, pilot, "config assistant claude")


@pytest.mark.parametrize("install", [_install_via_cli, _install_via_tui], ids=["cli", "tui"])
async def test_setting_the_assistant_installs_the_discovery_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], install
) -> None:
    workspace = init_workspace(tmp_path / "workspace").workspace

    await install(workspace, monkeypatch)

    path = discovery_path(_CLAUDE)
    assert path is not None
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert str(workspace.root) in text
