from __future__ import annotations

import os
import tomllib
from datetime import datetime
from pathlib import Path

from choom.core.assistants import resolve_assistant
from choom.core.config import LEGAL_ASSISTANT_VALUES
from choom.core.discovery import install_discovery_file, remove_discovery_files
from choom.core.errors import UsageError, WorkspaceError
from choom.core.models import InitResult, Workspace

SUPPORTED_SCHEMA = 1
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_GUIDANCE_TEMPLATES = {
    "AGENTS.md": _TEMPLATES_DIR / "AGENTS.md.tmpl",
    "CLAUDE.md": _TEMPLATES_DIR / "CLAUDE.md.tmpl",
}


def find_workspace(start: Path) -> Workspace:
    current = start.resolve()
    while True:
        marker = current / ".choom" / "config.toml"
        if marker.is_file():
            _check_schema(marker)
            return Workspace(root=current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    raise WorkspaceError(
        "no workspace found in this directory or any parent. Run 'choom init' to create one."
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


def init_workspace(target: Path, *, assistant: str | None = None) -> InitResult:
    """Create a workspace. When `assistant` is given, record it in the config (FR-027).

    Unchanged in every other respect. Never prompts.

    Raises:
        WorkspaceError: the directory is already a workspace.
        UsageError: `assistant` is not claude, copilot, or none. Nothing is created.
    """
    if assistant is not None and assistant not in LEGAL_ASSISTANT_VALUES:
        raise UsageError(
            f"assistant must be one of {', '.join(LEGAL_ASSISTANT_VALUES)}; got {assistant!r}"
        )

    target = target.resolve()
    choom_dir = target / ".choom"
    if choom_dir.exists():
        raise WorkspaceError(f"this directory is already a choom workspace: {target}")

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

    choom_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().replace(microsecond=0).isoformat()
    config_text = f'[workspace]\nschema = {SUPPORTED_SCHEMA}\ncreated = "{now}"\n'
    if assistant is not None:
        config_text += f'\n[assistant]\nname = "{assistant}"\n'
    (choom_dir / "config.toml").write_text(config_text, encoding="utf-8")

    workspace = Workspace(root=target)
    if assistant is not None:
        _install_or_remove_discovery(workspace, assistant)

    return InitResult(workspace=workspace, written=tuple(written), skipped=tuple(skipped))


def _install_or_remove_discovery(workspace: Workspace, assistant: str) -> None:
    """The discovery-file side effect of naming an assistant at init (US5, FR-020):
    `assistant` is a supported name installs its pointer at the new workspace;
    `"none"` installs nothing and removes any choom-owned file that happened to
    already exist. `init` with no `--assistant` never calls this at all.

    Never raises: a discovery-file failure must not fail workspace creation -- the
    workspace this function is called for already exists by this point. The file can
    always be installed later with `config assistant`.
    """
    try:
        if assistant == "none":
            remove_discovery_files()
            return
        profile = resolve_assistant(assistant).profile
        if profile is not None:
            install_discovery_file(workspace, profile)
    except WorkspaceError:
        pass
