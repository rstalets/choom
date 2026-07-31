from __future__ import annotations

from pathlib import Path

import endpaper.core


def _core_source_files() -> list[Path]:
    core_dir = Path(endpaper.core.__file__).parent
    return sorted(core_dir.rglob("*.py"))


def test_core_does_not_reference_sys_stdout() -> None:
    # ruff's TID251 banned-api rule (pyproject.toml) enforces the adapter-import ban;
    # it has no equivalent for a raw string reference, so that check stays a test.
    for path in _core_source_files():
        text = path.read_text(encoding="utf-8")
        assert "sys.stdout" not in text, f"{path} references sys.stdout"
