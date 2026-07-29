from __future__ import annotations

import os
import tomllib
from datetime import datetime
from pathlib import Path

from endpaper.core.errors import WorkspaceError
from endpaper.core.models import InitResult, Workspace

SUPPORTED_SCHEMA = 1
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_GUIDANCE_TEMPLATES = {
    "AGENTS.md": _TEMPLATES_DIR / "AGENTS.md.tmpl",
    "CLAUDE.md": _TEMPLATES_DIR / "CLAUDE.md.tmpl",
}


def find_workspace(start: Path) -> Workspace:
    current = start.resolve()
    while True:
        marker = current / ".endpaper" / "config.toml"
        if marker.is_file():
            _check_schema(marker)
            return Workspace(root=current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    raise WorkspaceError(
        "no workspace found in this directory or any parent. Run 'endpaper init' to create one."
    )


def _check_schema(marker: Path) -> None:
    with marker.open("rb") as f:
        data = tomllib.load(f)
    schema = data.get("workspace", {}).get("schema")
    if schema != SUPPORTED_SCHEMA:
        raise WorkspaceError(
            f"unsupported workspace schema {schema!r} in {marker}; "
            f"this build only supports schema {SUPPORTED_SCHEMA}"
        )


def _write_guidance_file(target: Path, name: str) -> bool:
    """Write one guidance file if absent. Returns True when written, False when an
    existing file was left untouched. Uses O_EXCL so the guarantee is enforced by the
    OS rather than a check-then-write race."""
    template = _GUIDANCE_TEMPLATES[name].read_text(encoding="utf-8")
    try:
        fd = os.open(target / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(template)
    return True


def init_workspace(target: Path) -> InitResult:
    target = target.resolve()
    endpaper_dir = target / ".endpaper"
    if endpaper_dir.exists():
        raise WorkspaceError(f"this directory is already an endpaper workspace: {target}")

    (target / "meetings").mkdir(parents=True, exist_ok=True)
    (target / "notes" / "daily").mkdir(parents=True, exist_ok=True)
    (target / "tasks.md").touch(exist_ok=True)

    written: list[str] = []
    skipped: list[str] = []
    for name in ("AGENTS.md", "CLAUDE.md"):
        if _write_guidance_file(target, name):
            written.append(name)
        else:
            skipped.append(name)

    endpaper_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().replace(microsecond=0).isoformat()
    (endpaper_dir / "config.toml").write_text(
        f'[workspace]\nschema = {SUPPORTED_SCHEMA}\ncreated = "{now}"\n',
        encoding="utf-8",
    )

    return InitResult(
        workspace=Workspace(root=target), written=tuple(written), skipped=tuple(skipped)
    )
