from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "endpaper", *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_every_command_terminates_promptly_with_stdin_closed(tmp_path: Path) -> None:
    assert _run(["init"], tmp_path).returncode == 0
    assert _run(["meeting", "new", "Q3 planning"], tmp_path).returncode == 0
    assert _run(["meeting", "list", "--json"], tmp_path).returncode == 0
    assert _run(["meeting", "list"], tmp_path).returncode == 0
    assert _run(["note", "today"], tmp_path).returncode == 0
    assert _run(["note", "new", "an idea"], tmp_path).returncode == 0
    assert _run(["note", "list", "--json"], tmp_path).returncode == 0
    assert _run(["note", "list"], tmp_path).returncode == 0
    result = _run(["task", "add", "buy milk"], tmp_path)
    assert result.returncode == 0
    task_id = result.stdout.strip()
    assert _run(["task", "list", "--json"], tmp_path).returncode == 0
    assert _run(["task", "list"], tmp_path).returncode == 0
    assert _run(["task", "done", task_id], tmp_path).returncode == 0
    assert _run(["task", "undone", task_id], tmp_path).returncode == 0
    assert _run(["--version"], tmp_path).returncode == 0
    assert _run(["--help"], tmp_path).returncode == 0
