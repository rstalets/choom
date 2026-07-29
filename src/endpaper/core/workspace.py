from __future__ import annotations

import tomllib
from datetime import datetime
from pathlib import Path

from endpaper.core.errors import WorkspaceError
from endpaper.core.models import Workspace

SUPPORTED_SCHEMA = 1
_TEMPLATE_PATH = Path(__file__).parent / "templates" / "AGENTS.md.tmpl"


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


def init_workspace(target: Path) -> Workspace:
    target = target.resolve()
    endpaper_dir = target / ".endpaper"
    if endpaper_dir.exists():
        raise WorkspaceError(f"this directory is already an endpaper workspace: {target}")

    (target / "meetings").mkdir(parents=True, exist_ok=True)
    (target / "notes" / "daily").mkdir(parents=True, exist_ok=True)
    (target / "tasks.md").touch(exist_ok=True)

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    (target / "AGENTS.md").write_text(template, encoding="utf-8")

    endpaper_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().replace(microsecond=0).isoformat()
    (endpaper_dir / "config.toml").write_text(
        f'[workspace]\nschema = {SUPPORTED_SCHEMA}\ncreated = "{now}"\n',
        encoding="utf-8",
    )

    return Workspace(root=target)
