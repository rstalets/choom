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


def test_all_names_are_actually_importable() -> None:
    for name in endpaper.core.__all__:
        assert hasattr(endpaper.core, name), f"{name} is in __all__ but not importable"


def test_links_public_surface_is_exported() -> None:
    for name in (
        "Link",
        "LinkDirection",
        "LinkReport",
        "LinkStatus",
        "LinkTarget",
        "check_links",
        "find_link_targets",
        "find_links",
        "heal_links",
        "heal_text",
        "inbound_links",
        "outbound_links",
        "relative_destination",
        "resolve_id",
        "resolve_link",
    ):
        assert name in endpaper.core.__all__, f"{name} missing from endpaper.core.__all__"
        assert hasattr(endpaper.core, name)


def test_mirrors_public_surface_is_exported() -> None:
    for name in (
        "Mirror",
        "MirrorReport",
        "MirrorResolution",
        "capture_task",
        "find_mirrors",
        "mirror_line",
        "propagate_to_documents",
        "reconcile_on_open",
        "reconcile_on_save",
        "write_document",
    ):
        assert name in endpaper.core.__all__, f"{name} missing from endpaper.core.__all__"
        assert hasattr(endpaper.core, name)
