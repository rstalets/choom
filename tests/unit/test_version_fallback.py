from __future__ import annotations

import builtins
import importlib
import sys


def test_version_falls_back_to_0_0_0_without_version_file(monkeypatch) -> None:
    """`__init__.py` must fall back to "0.0.0" when `_version.py` cannot be imported --
    the source-checkout case (FR-043), regardless of whether a stray `_version.py`
    happens to sit on disk in this environment."""
    monkeypatch.delitem(sys.modules, "endpaper", raising=False)
    monkeypatch.delitem(sys.modules, "endpaper._version", raising=False)

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "endpaper._version":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    module = importlib.import_module("endpaper")
    try:
        assert module.__version__ == "0.0.0"
    finally:
        monkeypatch.delitem(sys.modules, "endpaper", raising=False)
        importlib.import_module("endpaper")
