from __future__ import annotations

import sys
from typing import Any

import pytest

from choom.cli import main as main_module
from choom.core import workspace_title
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.list_screen import ListScreen
from choom.tui.terminal_title import CLEAR, POP, PUSH, SET
from tests.helpers import list_view


async def test_tui_opens_on_tasks_list(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)
        assert app.active == "tasks"


async def test_empty_workspace_shows_empty_state_message(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        labels = [str(item.children[0].content) for item in list_view(app).children]  # type: ignore[attr-defined]
        assert labels == ["No tasks yet. Press / then 'task <description>' to create one."]


class _FakeTTYStream:
    """A fake `sys.stdout` with a controllable `isatty()` that records every
    write, so the launcher's title wiring can be tested with no real terminal."""

    def __init__(self) -> None:
        self.written: list[str] = []

    def isatty(self) -> bool:
        return True

    def write(self, data: str) -> int:
        self.written.append(data)
        return len(data)

    def flush(self) -> None:
        pass


def _stub_launcher(monkeypatch: pytest.MonkeyPatch, workspace: Workspace) -> _FakeTTYStream:
    """Point `_run_tui()` at `workspace` and a fake TTY stdout, so `ChoomApp.run`
    is the only thing left to stub per test."""
    stream = _FakeTTYStream()
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(main_module, "find_workspace", lambda start: workspace)
    return stream


def _enter_bytes(workspace: Workspace) -> str:
    return PUSH + SET.format(title=workspace_title(workspace))


def _exit_bytes() -> str:
    return CLEAR + POP


# --- T008: enter bytes before run(), exit bytes after ----------------------


def test_title_is_set_before_run_and_restored_after_it_returns(
    monkeypatch: pytest.MonkeyPatch, tmp_workspace: Workspace
) -> None:
    stream = _stub_launcher(monkeypatch, tmp_workspace)
    observed_during_run: list[str] = []

    def fake_run(self: ChoomApp) -> None:
        # At the moment run() is entered, the enter bytes must already be
        # on the stream and the exit bytes must not be.
        observed_during_run.extend(stream.written)

    monkeypatch.setattr(ChoomApp, "run", fake_run)

    exit_code = main_module._run_tui()

    assert exit_code == 0
    assert observed_during_run == [_enter_bytes(tmp_workspace)]
    assert stream.written == [_enter_bytes(tmp_workspace), _exit_bytes()]


# --- T009: the three exit routes through _run_tui() -------------------------


def test_normal_return_from_run_restores_the_title_exactly_once(
    monkeypatch: pytest.MonkeyPatch, tmp_workspace: Workspace
) -> None:
    stream = _stub_launcher(monkeypatch, tmp_workspace)
    monkeypatch.setattr(ChoomApp, "run", lambda self: None)

    exit_code = main_module._run_tui()

    assert exit_code == 0
    assert stream.written == [_enter_bytes(tmp_workspace), _exit_bytes()]
    assert stream.written.count(_exit_bytes()) == 1


def test_keyboard_interrupt_out_of_run_restores_and_reraises(
    monkeypatch: pytest.MonkeyPatch, tmp_workspace: Workspace
) -> None:
    stream = _stub_launcher(monkeypatch, tmp_workspace)

    def fake_run(self: ChoomApp) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(ChoomApp, "run", fake_run)

    with pytest.raises(KeyboardInterrupt):
        main_module._run_tui()

    assert stream.written == [_enter_bytes(tmp_workspace), _exit_bytes()]
    assert stream.written.count(_exit_bytes()) == 1


def test_arbitrary_exception_out_of_run_restores_and_propagates(
    monkeypatch: pytest.MonkeyPatch, tmp_workspace: Workspace
) -> None:
    stream = _stub_launcher(monkeypatch, tmp_workspace)

    def fake_run(self: ChoomApp) -> None:
        raise RuntimeError("crashed")

    monkeypatch.setattr(ChoomApp, "run", fake_run)

    with pytest.raises(RuntimeError, match="crashed"):
        main_module._run_tui()

    assert stream.written == [_enter_bytes(tmp_workspace), _exit_bytes()]
    assert stream.written.count(_exit_bytes()) == 1


# --- T010: a cancelled quit (never leaving run()) must not restore ---------


def test_a_run_that_never_returns_yet_does_not_restore(
    monkeypatch: pytest.MonkeyPatch, tmp_workspace: Workspace
) -> None:
    """FR-012, in its non-tautological form: while `run()` is still executing --
    the state a cancelled `ctrl+q` confirmation leaves the app in -- the stream
    must hold the enter bytes and must not hold CLEAR or POP. This fails an
    implementation that restores from `on_unmount`, an eager `atexit`, or
    anywhere other than actually leaving `run()`, which a cancelled
    confirmation never does."""
    stream = _stub_launcher(monkeypatch, tmp_workspace)
    observed: dict[str, Any] = {}

    def fake_run(self: ChoomApp) -> None:
        observed["written"] = list(stream.written)

    monkeypatch.setattr(ChoomApp, "run", fake_run)

    main_module._run_tui()

    assert observed["written"] == [_enter_bytes(tmp_workspace)]
    assert CLEAR not in "".join(observed["written"])
    assert POP not in "".join(observed["written"])
