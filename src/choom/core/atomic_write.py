"""The one atomic-write primitive every write path in `core` shares.

Before this module existed, the same same-directory-temp-file-plus-`os.replace`
sequence was implemented four times over (`tasks.py`, `editing.py`, `config.py`,
and `links.py`), each with slightly different exception handling -- meaning an
atomic-write bug had four places it could be fixed, and three places it could
still be lurking after the first fix. This is the one place now.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from choom.core.errors import WorkspaceError


def write_text_atomic(path: Path, text: str) -> None:
    """Write `text` to `path` atomically: a same-directory temp file, then
    `os.replace`, so a crash mid-write never leaves a partial file at `path`.
    Creates `path`'s parent directory first if it does not already exist.

    Raises:
        WorkspaceError: the directory, the temp file, or the replace could not
            be completed. The temp file is always cleaned up first -- on any
            exception, not just an I/O failure -- so a crash never leaves a
            stray `.tmp` file behind for someone else to find later.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", newline="", dir=path.parent, delete=False, suffix=".tmp"
            ) as tmp_file:
                tmp_file.write(text)
                tmp_path = Path(tmp_file.name)
            os.replace(tmp_path, path)
        except BaseException:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            raise
    except (PermissionError, OSError) as exc:
        raise WorkspaceError(f"could not write {path}: {exc}") from exc
