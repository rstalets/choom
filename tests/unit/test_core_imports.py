from __future__ import annotations

import ast
from pathlib import Path

import endpaper.core

FORBIDDEN_MODULES = {"argparse", "textual", "rich"}


def _core_source_files() -> list[Path]:
    core_dir = Path(endpaper.core.__file__).parent
    return sorted(core_dir.rglob("*.py"))


def test_core_does_not_import_adapter_modules() -> None:
    for path in _core_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in FORBIDDEN_MODULES, f"{path} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                assert root not in FORBIDDEN_MODULES, f"{path} imports from {node.module}"


def test_core_does_not_reference_sys_stdout() -> None:
    for path in _core_source_files():
        text = path.read_text(encoding="utf-8")
        assert "sys.stdout" not in text, f"{path} references sys.stdout"
