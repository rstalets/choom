from __future__ import annotations

import os
import secrets
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pytest

from choom.cli.main import main
from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.workspace import init_workspace

#: The fixed reply `stub_assistant`'s "reply" mode prints, so integration tests can
#: assert on insertion, ordering, and line endings without duplicating the text.
STUB_REPLY_TEXT = "line one\nline two\nline three"

_STUB_SOURCE = """\
#!{python}
import os
import sys
import time

mode = os.environ.get("CHOOM_STUB_MODE", "echo")

if mode == "echo":
    for arg in sys.argv[1:]:
        print(arg)
    sys.exit(0)
elif mode == "reply":
    print("line one\\nline two\\nline three")
    sys.exit(0)
elif mode == "reply_with_slash":
    print("/ai nested attempt\\nstill here")
    sys.exit(0)
elif mode == "empty":
    sys.exit(0)
elif mode == "fail":
    print("stub failure", file=sys.stderr)
    sys.exit(1)
elif mode == "sleep":
    time.sleep(3600)
else:
    sys.exit(0)
"""


@pytest.fixture
def stub_assistant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    """Install a fake `claude` on PATH, isolated from the host's real assistant CLIs.

    A small Python script written to `tmp_path`, made executable, and named as the
    `claude` profile's binary, so `shutil.which` finds it for real -- detection and
    invocation are exercised for real rather than mocked. `PATH` is replaced entirely
    (not prepended) so a host machine with other assistant CLIs installed -- e.g. a
    real `copilot` alongside the stub `claude` -- can't make `available_assistants()`
    return more than this one stub. The shebang points at the running interpreter
    directly rather than through `env python3`, so the stub still starts once `PATH`
    no longer has a `python3` on it.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / ("claude.cmd" if os.name == "nt" else "claude")
    script.write_text(_STUB_SOURCE.format(python=sys.executable), encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    monkeypatch.setenv("CHOOM_STUB_MODE", "echo")

    def _set_mode(mode: str) -> None:
        monkeypatch.setenv("CHOOM_STUB_MODE", mode)

    return _set_mode


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Workspace:
    return init_workspace(tmp_path).workspace


@dataclass(frozen=True)
class Result:
    """One CLI invocation: its exit code and its two streams, both stripped."""

    exit_code: int
    out: str
    err: str


class Cli:
    """Runs CLI commands inside an already-initialised workspace.

    Replaces the `monkeypatch.chdir(...)` / `main(["init"])` /
    `capsys.readouterr()` prologue that every CLI test used to repeat.
    """

    def __init__(self, root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        self.root = root
        self._capsys = capsys

    def __call__(self, *argv: str) -> Result:
        exit_code = main(list(argv))
        captured = self._capsys.readouterr()
        return Result(exit_code, captured.out.strip(), captured.err.strip())

    def read(self, relative: str | Path) -> str:
        """Read a file the CLI just reported, by its workspace-relative path."""
        return (self.root / relative).read_text(encoding="utf-8")


@pytest.fixture
def cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> Cli:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    return Cli(tmp_path, capsys)


@pytest.fixture
def frozen_now() -> datetime:
    return datetime(2026, 7, 28, 9, 14, 0)


@pytest.fixture
def seeded_id(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    fixed = "a1b2c3d4"
    monkeypatch.setattr(secrets, "token_hex", lambda n: fixed)
    yield fixed


@pytest.fixture
def sample_document(tmp_workspace: Workspace) -> Path:
    meeting = create_meeting(tmp_workspace, "sample meeting", type="standup")
    return meeting.path


def write_raw(path: Path, text: str, *, newline: str) -> None:
    """Write `text` (authored with plain "\\n") to `path` using `newline` as the line
    ending, with Python's own newline translation switched off so the bytes on disk are
    exactly what was requested -- no double translation."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\n", newline))


def daily_note_path(workspace: Workspace, day: date) -> Path:
    return workspace.daily_dir / f"{day:%Y/%m}" / f"{day:%Y-%m-%d}.md"


def tasks_file(workspace: Workspace) -> Path:
    return workspace.root / "tasks.md"


def write_tasks(workspace: Workspace, text: str, *, newline: str = "\n") -> Path:
    path = tasks_file(workspace)
    with open(path, "w", encoding="utf-8", newline=newline) as fh:
        fh.write(text)
    return path
